import logging
import time

import httpx

from app.models import ReviewComment, Severity, SEVERITY_EMOJI
from app.github.client import GitHubClient
from app.github.diff_parser import parse_unified_diff
from app.github.position_mapper import map_line_to_position, find_nearest_position
from app.analysis.chunker import chunk_python_code, chunk_by_blocks
from app.analysis.llm import LLMReviewer

logger = logging.getLogger(__name__)

SKIP_PATTERNS = [
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum",
    "Pipfile.lock", "poetry.lock", "composer.lock",
    ".min.js", ".min.css", ".map",
    "__pycache__", ".pyc", "node_modules/",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    "migrations/", "generated/", "vendor/", "dist/", "build/",
]


def _should_skip(path: str, extra_ignores: list[str] | None = None) -> bool:
    patterns = SKIP_PATTERNS + (extra_ignores or [])
    return any(p in path for p in patterns)


async def run_review(
    owner: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    github: GitHubClient,
    llm: LLMReviewer,
    profile: str = "all",
    max_files: int = 20,
    max_concurrent: int = 5,
    exclude: list[str] | None = None,
) -> dict:
    """Run a full review on a pull request. Returns a summary dict."""

    start = time.time()

    diff_text = await github.get_pr_diff(owner, repo, pr_number)
    diff_files = parse_unified_diff(diff_text)

    all_issues: list[ReviewComment] = []
    all_positioned: list[dict] = []
    files_reviewed = 0
    files_skipped = 0

    for diff_file in diff_files:
        if files_reviewed >= max_files:
            break

        if _should_skip(diff_file.path, exclude):
            files_skipped += 1
            continue

        try:
            content = await github.get_file_content(owner, repo, diff_file.path, head_sha)
        except httpx.HTTPStatusError:
            files_skipped += 1
            continue

        if diff_file.language == "python":
            chunks = chunk_python_code(content, diff_file.path)
        else:
            chunks = chunk_by_blocks(content, diff_file.path)

        changed_lines = {ln for ln, _ in diff_file.added_lines}
        relevant = [
            c for c in chunks
            if any(c.start_line <= ln <= c.end_line for ln in changed_lines)
        ]

        if not relevant:
            files_skipped += 1
            continue

        issues = await llm.review_chunks(relevant, profile=profile, max_concurrent=max_concurrent)

        file_lines = content.splitlines()
        for issue in issues:
            params = map_line_to_position(diff_file, issue.line)
            if params is None:
                params = find_nearest_position(diff_file, issue.line)
            if params is None:
                continue

            ctx_start = max(0, issue.line - 1 - 4)
            ctx_end = min(len(file_lines), issue.line + 4)
            issue.code_context = "\n".join(
                f"{i + 1}|{file_lines[i]}" for i in range(ctx_start, ctx_end)
            )

            all_issues.append(issue)
            all_positioned.append({**params, "issue": issue})

        files_reviewed += 1

    body, inline = build_review_body(all_positioned)

    if body or inline:
        await github.post_review(owner, repo, pr_number, head_sha, inline, body)

    elapsed = int((time.time() - start) * 1000)

    logger.info(
        "Review complete: %s/%s#%d — %d issues, %d inline, %d files, %dms",
        owner, repo, pr_number, len(all_issues), len(inline), files_reviewed, elapsed,
    )

    return {
        "issues": len(all_issues),
        "inline_comments": len(inline),
        "files_reviewed": files_reviewed,
        "files_skipped": files_skipped,
        "time_ms": elapsed,
    }


def build_review_body(positioned: list[dict]) -> tuple[str, list[dict]]:
    """Build the markdown summary and inline comments for a GitHub review.
    Returns (body_markdown, inline_comments_list)."""

    if not positioned:
        return "", []

    by_file: dict[str, list[dict]] = {}
    for c in positioned:
        by_file.setdefault(c.get("path", ""), []).append(c)

    total = len(positioned)
    crit_high = sum(1 for c in positioned if c["issue"].severity.value in ("critical", "high"))

    parts = [
        "## \U0001f916 AI Code Review\n",
        f"Found **{total} issue{'s' if total != 1 else ''}** across "
        f"**{len(by_file)} file{'s' if len(by_file) != 1 else ''}**",
    ]
    if crit_high:
        parts.append(f" — **{crit_high} require attention**")
    parts.append("\n")

    for path, entries in by_file.items():
        entries.sort(key=lambda e: e["issue"].line)
        parts.append(f"\n### `{path}`\n")
        for e in entries:
            iss = e["issue"]
            emoji = SEVERITY_EMOJI.get(iss.severity, "")
            parts.append(f"- {emoji} **L{iss.line}** [{iss.severity.value.upper()}]: {iss.issue}")
            parts.append(f"  > {iss.suggestion}\n")

    body = "\n".join(parts)

    inline = []
    for c in positioned:
        iss = c["issue"]
        if iss.severity.value not in ("critical", "high"):
            continue
        emoji = SEVERITY_EMOJI.get(iss.severity, "")
        comment: dict = {
            "path": c.get("path", ""),
            "body": f"{emoji} **{iss.severity.value.upper()}**: {iss.issue}\n\n**Fix:** {iss.suggestion}",
        }
        if "line" in c:
            comment["line"] = c["line"]
        if "side" in c:
            comment["side"] = c["side"]
        inline.append(comment)

    return body, inline

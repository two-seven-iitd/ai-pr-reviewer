"""Entry point for the GitHub Action.

Reads the PR context from GitHub's environment variables,
runs the AI review, and posts comments on the pull request.
"""

import asyncio
import json
import logging
import os
import sys

from app.github.client import GitHubClient
from app.analysis.llm import LLMReviewer
from app.review import run_review


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ai-pr-reviewer")


def get_input(name: str, default: str = "") -> str:
    return os.environ.get(f"INPUT_{name.upper()}", default)


async def main():
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("INPUT_GITHUB_TOKEN", "")
    if not github_token:
        logger.error("GITHUB_TOKEN is not set. Make sure the action has 'contents: read' and 'pull-requests: write' permissions.")
        sys.exit(1)

    api_key = get_input("openrouter_api_key")
    if not api_key:
        logger.error("openrouter_api_key input is required.")
        sys.exit(1)

    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path:
        logger.error("GITHUB_EVENT_PATH not set — are you running this inside a GitHub Action?")
        sys.exit(1)

    with open(event_path) as f:
        event = json.load(f)

    if "pull_request" not in event:
        logger.info("Not a pull_request event — skipping.")
        return

    pr = event["pull_request"]
    repo_full = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo_full:
        logger.error("GITHUB_REPOSITORY not set correctly: %s", repo_full)
        sys.exit(1)

    owner, repo = repo_full.split("/", 1)
    pr_number = pr["number"]
    head_sha = pr["head"]["sha"]

    model = get_input("model", "deepseek/deepseek-v4-flash")
    profile = get_input("profile", "all")
    max_files = int(get_input("max_files", "20"))
    max_concurrent = int(get_input("max_concurrent", "5"))
    exclude_raw = get_input("exclude", "")
    exclude = [p.strip() for p in exclude_raw.split(",") if p.strip()] if exclude_raw else []

    logger.info("Reviewing %s/%s#%d (commit %s)", owner, repo, pr_number, head_sha[:8])
    logger.info("Model: %s | Profile: %s | Max files: %d", model, profile, max_files)

    github = GitHubClient(github_token)
    llm = LLMReviewer(api_key, model)

    await github.start()
    await llm.start()

    try:
        result = await run_review(
            owner=owner, repo=repo, pr_number=pr_number, head_sha=head_sha,
            github=github, llm=llm,
            profile=profile, max_files=max_files,
            max_concurrent=max_concurrent, exclude=exclude,
        )

        logger.info(
            "Done — %d issues found, %d inline comments posted, %d files reviewed (%dms)",
            result["issues"], result["inline_comments"],
            result["files_reviewed"], result["time_ms"],
        )

        output_file = os.environ.get("GITHUB_OUTPUT", "")
        if output_file:
            with open(output_file, "a") as f:
                f.write(f"issues={result['issues']}\n")
                f.write(f"comments={result['inline_comments']}\n")
                f.write(f"files_reviewed={result['files_reviewed']}\n")
                f.write(f"time_ms={result['time_ms']}\n")

    finally:
        await github.close()
        await llm.close()


if __name__ == "__main__":
    asyncio.run(main())

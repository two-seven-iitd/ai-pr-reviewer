from app.models import CodeChunk

SYSTEM_PROMPT = """You are a senior software engineer performing a code review on a pull request.
Your job is to identify bugs, security vulnerabilities, performance issues, and violations of best practices.

Rules:
- Focus ONLY on the code provided. Do not invent issues.
- Only flag genuine problems, not style preferences.
- Be specific: reference exact line numbers, variable names, and function names.
- For each issue, provide a concrete fix, not vague advice.
- Respond ONLY with a JSON array. No other text, no markdown fences, no explanation.

Each object in the array must have exactly these fields:
{
    "line": <int>,
    "severity": "<low|medium|high|critical>",
    "issue": "<one sentence describing the problem>",
    "suggestion": "<concrete code or instruction to fix it>"
}

If the code has no issues, respond with an empty array: []

Severity guide:
- critical: Security vulnerabilities (SQL injection, XSS, auth bypass, secrets in code)
- high: Bugs that will cause crashes or data corruption in production
- medium: Performance issues, resource leaks, error handling gaps
- low: Code that works but could be cleaner or more maintainable"""

PROFILE_FOCUS = {
    "security": "Focus ONLY on security vulnerabilities: SQL injection, XSS, CSRF, auth issues, secrets exposure, insecure deserialization, path traversal.",
    "performance": "Focus ONLY on performance issues: N+1 queries, unnecessary allocations, blocking I/O, missing caching, inefficient algorithms.",
    "bugs": "Focus ONLY on bugs: null references, off-by-one errors, race conditions, unhandled exceptions, incorrect logic, type errors.",
    "style": "Focus ONLY on code quality: naming, DRY violations, function length, complexity, missing error handling.",
    "all": "Check for all issue types: security, bugs, performance, and code quality.",
}


def build_review_prompt(chunk: CodeChunk, profile: str = "all") -> str:
    focus = PROFILE_FOCUS.get(profile, PROFILE_FOCUS["all"])
    numbered = _add_line_numbers(chunk.code, chunk.start_line)
    ext = chunk.file_path.rsplit(".", 1)[-1].upper() if "." in chunk.file_path else "TEXT"

    return (
        f"Review this {ext} code from file `{chunk.file_path}` "
        f"(lines {chunk.start_line}-{chunk.end_line}).\n\n"
        f"{focus}\n\n"
        f"CODE (line numbers are absolute file line numbers):\n"
        f"```\n{numbered}\n```\n\n"
        f'Respond with a JSON array of issues. '
        f'Remember: "line" values must match the line numbers shown above.'
    )


def _add_line_numbers(code: str, start_line: int) -> str:
    return "\n".join(
        f"{start_line + i:4d} | {line}"
        for i, line in enumerate(code.splitlines())
    )

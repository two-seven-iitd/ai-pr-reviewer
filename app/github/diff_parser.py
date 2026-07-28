import re

from app.models import DiffFile

LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".jsx": "javascript",
    ".go": "go", ".rs": "rust", ".java": "java",
    ".cpp": "cpp", ".c": "c", ".rb": "ruby",
    ".php": "php", ".swift": "swift", ".kt": "kotlin",
    ".cs": "csharp", ".scala": "scala", ".sh": "bash",
}


def detect_language(path: str) -> str:
    for ext, lang in LANGUAGE_MAP.items():
        if path.endswith(ext):
            return lang
    return "unknown"


def parse_unified_diff(diff_text: str) -> list[DiffFile]:
    files: list[DiffFile] = []
    current_file: DiffFile | None = None
    current_hunk: dict | None = None
    diff_position = 0
    line_new = 0
    line_old = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
            diff_position = 0
            current_file = DiffFile(path="", added_lines=[], removed_lines=[], hunks=[])
            current_hunk = None

        elif line.startswith("+++ b/") and current_file is not None:
            current_file.path = line[6:]
            current_file.language = detect_language(current_file.path)

        elif line.startswith("@@") and current_file is not None:
            diff_position += 1
            match = re.match(r"@@ -(\d+),?\d* \+(\d+),?\d* @@", line)
            if match:
                line_old = int(match.group(1))
                line_new = int(match.group(2))
                current_hunk = {
                    "old_start": line_old,
                    "new_start": line_new,
                    "diff_start_position": diff_position,
                    "lines": [],
                }
                current_file.hunks.append(current_hunk)

        elif line.startswith("+") and not line.startswith("+++") and current_hunk is not None:
            diff_position += 1
            current_file.added_lines.append((line_new, line[1:]))
            current_hunk["lines"].append({
                "type": "add", "content": line[1:],
                "new_line": line_new, "diff_position": diff_position,
            })
            line_new += 1

        elif line.startswith("-") and not line.startswith("---") and current_hunk is not None:
            diff_position += 1
            current_file.removed_lines.append((line_old, line[1:]))
            current_hunk["lines"].append({
                "type": "remove", "content": line[1:],
                "old_line": line_old, "diff_position": diff_position,
            })
            line_old += 1

        elif current_hunk is not None:
            diff_position += 1
            current_hunk["lines"].append({
                "type": "context",
                "content": line[1:] if line.startswith(" ") else line,
                "old_line": line_old, "new_line": line_new,
                "diff_position": diff_position,
            })
            line_old += 1
            line_new += 1

    if current_file:
        files.append(current_file)

    return [f for f in files if f.path]

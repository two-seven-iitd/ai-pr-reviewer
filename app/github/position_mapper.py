from app.models import DiffFile


def map_line_to_position(diff_file: DiffFile, target_line: int) -> dict | None:
    """Map a source line number to GitHub review comment parameters."""
    for hunk in diff_file.hunks:
        for diff_line in hunk["lines"]:
            if diff_line["type"] in ("add", "context"):
                if diff_line.get("new_line") == target_line:
                    return {
                        "path": diff_file.path,
                        "line": target_line,
                        "side": "RIGHT",
                    }
    return None


def find_nearest_position(diff_file: DiffFile, target_line: int, max_distance: int = 5) -> dict | None:
    """Find the closest commentable line within max_distance lines."""
    best = None
    best_distance = float("inf")

    for hunk in diff_file.hunks:
        for diff_line in hunk["lines"]:
            if diff_line["type"] in ("add", "context"):
                new_line = diff_line.get("new_line")
                if new_line is not None:
                    distance = abs(new_line - target_line)
                    if distance < best_distance:
                        best_distance = distance
                        best = {"path": diff_file.path, "line": new_line, "side": "RIGHT"}

    if best and best_distance <= max_distance:
        return best
    return None

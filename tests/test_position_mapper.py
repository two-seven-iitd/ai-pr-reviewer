from app.models import DiffFile
from app.github.position_mapper import map_line_to_position, find_nearest_position


def _make_diff_file() -> DiffFile:
    """Create a DiffFile with a hunk spanning lines 10-15."""
    return DiffFile(
        path="app/main.py",
        added_lines=[(11, "new line"), (12, "another new")],
        removed_lines=[(10, "old line")],
        hunks=[{
            "old_start": 10,
            "new_start": 10,
            "diff_start_position": 1,
            "lines": [
                {"type": "context", "content": "ctx", "old_line": 10, "new_line": 10, "diff_position": 2},
                {"type": "add", "content": "new line", "new_line": 11, "diff_position": 3},
                {"type": "add", "content": "another new", "new_line": 12, "diff_position": 4},
                {"type": "context", "content": "ctx2", "old_line": 11, "new_line": 13, "diff_position": 5},
                {"type": "context", "content": "ctx3", "old_line": 12, "new_line": 14, "diff_position": 6},
            ],
        }],
    )


class TestMapLineToPosition:
    def test_exact_match_on_added_line(self):
        result = map_line_to_position(_make_diff_file(), 11)
        assert result is not None
        assert result["line"] == 11
        assert result["path"] == "app/main.py"
        assert result["side"] == "RIGHT"

    def test_exact_match_on_context_line(self):
        result = map_line_to_position(_make_diff_file(), 10)
        assert result is not None
        assert result["line"] == 10

    def test_no_match_outside_hunk(self):
        result = map_line_to_position(_make_diff_file(), 100)
        assert result is None

    def test_no_match_on_removed_line_number(self):
        df = _make_diff_file()
        df.hunks[0]["lines"] = [
            {"type": "remove", "content": "old", "old_line": 5, "diff_position": 1},
        ]
        result = map_line_to_position(df, 5)
        assert result is None


class TestFindNearestPosition:
    def test_finds_nearby_line(self):
        result = find_nearest_position(_make_diff_file(), 15)
        assert result is not None
        assert result["line"] == 14

    def test_respects_max_distance(self):
        result = find_nearest_position(_make_diff_file(), 100, max_distance=5)
        assert result is None

    def test_returns_closest(self):
        result = find_nearest_position(_make_diff_file(), 13)
        assert result is not None
        assert result["line"] == 13

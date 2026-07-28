from app.models import ReviewComment, Severity
from app.review import build_review_body


def _make_positioned(severity: str = "high", line: int = 10, path: str = "app/main.py") -> dict:
    return {
        "path": path,
        "line": line,
        "side": "RIGHT",
        "issue": ReviewComment(
            file=path, line=line,
            severity=Severity(severity),
            issue="Potential null reference",
            suggestion="Add a null check before accessing",
        ),
    }


class TestBuildReviewBody:
    def test_empty_returns_empty(self):
        body, inline = build_review_body([])
        assert body == ""
        assert inline == []

    def test_single_critical_issue(self):
        body, inline = build_review_body([_make_positioned("critical")])
        assert "1 issue" in body
        assert "1 file" in body
        assert "require attention" in body
        assert len(inline) == 1

    def test_low_severity_not_inline(self):
        body, inline = build_review_body([_make_positioned("low")])
        assert len(inline) == 0
        assert "1 issue" in body

    def test_medium_severity_not_inline(self):
        body, inline = build_review_body([_make_positioned("medium")])
        assert len(inline) == 0

    def test_high_severity_is_inline(self):
        body, inline = build_review_body([_make_positioned("high")])
        assert len(inline) == 1
        assert inline[0]["path"] == "app/main.py"
        assert inline[0]["line"] == 10

    def test_mixed_severities(self):
        positioned = [
            _make_positioned("critical", line=5),
            _make_positioned("high", line=10),
            _make_positioned("medium", line=15),
            _make_positioned("low", line=20),
        ]
        body, inline = build_review_body(positioned)
        assert "4 issues" in body
        assert len(inline) == 2  # only critical + high

    def test_high_issues_in_table(self):
        body, _ = build_review_body([_make_positioned("critical")])
        assert "| Line |" in body
        assert "**Issues**" in body

    def test_low_issues_in_suggestions(self):
        body, _ = build_review_body([_make_positioned("low")])
        assert "**Suggestions**" in body
        assert "| Line |" not in body

    def test_multiple_files(self):
        positioned = [
            _make_positioned("high", path="a.py"),
            _make_positioned("high", path="b.py"),
        ]
        body, inline = build_review_body(positioned)
        assert "2 files" in body
        assert "`a.py`" in body
        assert "`b.py`" in body

    def test_inline_comment_has_fix(self):
        _, inline = build_review_body([_make_positioned("critical")])
        assert "**Fix:**" in inline[0]["body"]

    def test_body_contains_issue_text(self):
        body, _ = build_review_body([_make_positioned("high")])
        assert "Potential null reference" in body

    def test_plural_handling_single(self):
        body, _ = build_review_body([_make_positioned("low")])
        assert "1 issue" in body
        assert "1 file" in body
        assert "issues" not in body

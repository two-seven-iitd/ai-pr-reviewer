from app.models import CodeChunk
from app.analysis.prompts import build_review_prompt, PROFILE_FOCUS


class TestBuildReviewPrompt:
    def test_includes_file_path(self):
        chunk = CodeChunk(
            file_path="app/auth.py", code="def login():\n    pass",
            start_line=1, end_line=2, chunk_type="function",
        )
        prompt = build_review_prompt(chunk)
        assert "app/auth.py" in prompt

    def test_includes_line_numbers(self):
        chunk = CodeChunk(
            file_path="f.py", code="a = 1\nb = 2",
            start_line=10, end_line=11, chunk_type="block",
        )
        prompt = build_review_prompt(chunk)
        assert "  10 |" in prompt
        assert "  11 |" in prompt

    def test_uses_profile_focus(self):
        chunk = CodeChunk(
            file_path="f.py", code="x = 1",
            start_line=1, end_line=1, chunk_type="block",
        )
        prompt = build_review_prompt(chunk, profile="security")
        assert "security" in prompt.lower()

    def test_defaults_to_all_profile(self):
        chunk = CodeChunk(
            file_path="f.py", code="x = 1",
            start_line=1, end_line=1, chunk_type="block",
        )
        prompt = build_review_prompt(chunk)
        assert PROFILE_FOCUS["all"] in prompt

    def test_detects_file_extension(self):
        chunk = CodeChunk(
            file_path="app/main.go", code="package main",
            start_line=1, end_line=1, chunk_type="block",
        )
        prompt = build_review_prompt(chunk)
        assert "GO" in prompt

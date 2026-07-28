from app.github.diff_parser import parse_unified_diff, detect_language


SAMPLE_DIFF = """\
diff --git a/app/utils.py b/app/utils.py
--- a/app/utils.py
+++ b/app/utils.py
@@ -10,6 +10,8 @@ import os

 def process_data(items):
-    result = []
+    result = {}
+    seen = set()
     for item in items:
+        if item.id in seen:
+            continue
         result[item.id] = item
"""

MULTI_FILE_DIFF = """\
diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 import sys
+import os

 def main():
diff --git a/src/utils.ts b/src/utils.ts
--- a/src/utils.ts
+++ b/src/utils.ts
@@ -5,3 +5,4 @@ export function helper() {
   const x = 1;
   const y = 2;
+  const z = x + y;
   return x;
"""


class TestParseUnifiedDiff:
    def test_parses_single_file(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert len(files) == 1
        assert files[0].path == "app/utils.py"

    def test_detects_language(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert files[0].language == "python"

    def test_extracts_added_lines(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        added_contents = [content for _, content in files[0].added_lines]
        assert "    result = {}" in added_contents
        assert "    seen = set()" in added_contents

    def test_extracts_removed_lines(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        removed_contents = [content for _, content in files[0].removed_lines]
        assert "    result = []" in removed_contents

    def test_parses_multiple_files(self):
        files = parse_unified_diff(MULTI_FILE_DIFF)
        assert len(files) == 2
        assert files[0].path == "src/main.py"
        assert files[1].path == "src/utils.ts"

    def test_second_file_language(self):
        files = parse_unified_diff(MULTI_FILE_DIFF)
        assert files[1].language == "typescript"

    def test_creates_hunks(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert len(files[0].hunks) == 1
        hunk = files[0].hunks[0]
        assert hunk["old_start"] == 10
        assert hunk["new_start"] == 10

    def test_empty_diff_returns_empty(self):
        assert parse_unified_diff("") == []

    def test_diff_with_no_changes_returns_empty(self):
        assert parse_unified_diff("some random text\nno diff here") == []

    def test_hunk_lines_have_diff_positions(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        hunk = files[0].hunks[0]
        for line in hunk["lines"]:
            assert "diff_position" in line
            assert "type" in line
            assert line["type"] in ("add", "remove", "context")


class TestDetectLanguage:
    def test_python(self):
        assert detect_language("app/main.py") == "python"

    def test_typescript(self):
        assert detect_language("src/utils.ts") == "typescript"

    def test_tsx(self):
        assert detect_language("App.tsx") == "typescript"

    def test_unknown(self):
        assert detect_language("Makefile") == "unknown"

    def test_nested_path(self):
        assert detect_language("a/b/c/deep.go") == "go"

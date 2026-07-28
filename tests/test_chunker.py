from app.analysis.chunker import chunk_python_code, chunk_by_blocks, hash_content


PYTHON_SOURCE = """\
import os

def greet(name):
    return f"Hello, {name}"

class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

def farewell(name):
    return f"Bye, {name}"
"""

INVALID_PYTHON = """\
def broken(:
    this is not valid python
    if True
        pass
"""


class TestChunkPythonCode:
    def test_extracts_functions_and_classes(self):
        chunks = chunk_python_code(PYTHON_SOURCE, "example.py")
        names = [c.name for c in chunks]
        assert "greet" in names
        assert "Calculator" in names
        assert "farewell" in names

    def test_function_chunk_type(self):
        chunks = chunk_python_code(PYTHON_SOURCE, "example.py")
        greet = next(c for c in chunks if c.name == "greet")
        assert greet.chunk_type == "function"

    def test_class_chunk_type(self):
        chunks = chunk_python_code(PYTHON_SOURCE, "example.py")
        calc = next(c for c in chunks if c.name == "Calculator")
        assert calc.chunk_type == "class"

    def test_line_numbers_are_correct(self):
        chunks = chunk_python_code(PYTHON_SOURCE, "example.py")
        greet = next(c for c in chunks if c.name == "greet")
        assert greet.start_line == 3
        assert greet.end_line == 4

    def test_falls_back_on_syntax_error(self):
        chunks = chunk_python_code(INVALID_PYTHON, "broken.py")
        assert len(chunks) > 0
        assert all(c.chunk_type == "block" for c in chunks)

    def test_file_path_preserved(self):
        chunks = chunk_python_code(PYTHON_SOURCE, "src/utils.py")
        assert all(c.file_path == "src/utils.py" for c in chunks)


class TestChunkByBlocks:
    def test_small_file_single_chunk(self):
        source = "\n".join(f"line {i}" for i in range(10))
        chunks = chunk_by_blocks(source, "small.txt", max_lines=60)
        assert len(chunks) == 1

    def test_large_file_multiple_chunks(self):
        source = "\n".join(f"line {i}" for i in range(150))
        chunks = chunk_by_blocks(source, "big.txt", max_lines=60, overlap=5)
        assert len(chunks) > 1

    def test_overlap_between_chunks(self):
        source = "\n".join(f"line {i}" for i in range(120))
        chunks = chunk_by_blocks(source, "f.txt", max_lines=60, overlap=5)
        assert chunks[1].start_line == 56  # 60 - 5 + 1

    def test_empty_source(self):
        chunks = chunk_by_blocks("", "empty.txt")
        assert chunks == []

    def test_line_numbers_start_at_one(self):
        source = "a\nb\nc"
        chunks = chunk_by_blocks(source, "f.txt")
        assert chunks[0].start_line == 1


class TestHashContent:
    def test_deterministic(self):
        assert hash_content("hello") == hash_content("hello")

    def test_different_content_different_hash(self):
        assert hash_content("hello") != hash_content("world")

    def test_returns_hex_string(self):
        h = hash_content("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

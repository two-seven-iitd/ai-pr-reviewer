import ast
import hashlib

from app.models import CodeChunk


def chunk_python_code(source: str, file_path: str) -> list[CodeChunk]:
    """Split Python source into function/class-level chunks using AST parsing.
    Falls back to block-based chunking on syntax errors."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return chunk_by_blocks(source, file_path)

    lines = source.splitlines()
    chunks = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk_lines = lines[node.lineno - 1 : node.end_lineno]
            chunks.append(CodeChunk(
                file_path=file_path,
                code="\n".join(chunk_lines),
                start_line=node.lineno,
                end_line=node.end_lineno,
                chunk_type="function",
                name=node.name,
            ))
        elif isinstance(node, ast.ClassDef):
            chunk_lines = lines[node.lineno - 1 : node.end_lineno]
            chunks.append(CodeChunk(
                file_path=file_path,
                code="\n".join(chunk_lines),
                start_line=node.lineno,
                end_line=node.end_lineno,
                chunk_type="class",
                name=node.name,
            ))

    return chunks if chunks else chunk_by_blocks(source, file_path)


def chunk_by_blocks(
    source: str, file_path: str, max_lines: int = 60, overlap: int = 5,
) -> list[CodeChunk]:
    """Split source into fixed-size blocks with overlap for boundary coverage."""
    lines = source.splitlines()
    if not lines:
        return []

    chunks = []
    i = 0
    while i < len(lines):
        end = min(i + max_lines, len(lines))
        chunks.append(CodeChunk(
            file_path=file_path,
            code="\n".join(lines[i:end]),
            start_line=i + 1,
            end_line=end,
            chunk_type="block",
        ))
        if end >= len(lines):
            break
        i = end - overlap

    return chunks


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()

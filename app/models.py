from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_EMOJI = {
    Severity.CRITICAL: "\U0001f6a8",
    Severity.HIGH: "\U0001f534",
    Severity.MEDIUM: "\U0001f7e1",
    Severity.LOW: "\U0001f535",
}


class ReviewComment(BaseModel):
    file: str
    line: int
    severity: Severity
    issue: str
    suggestion: str
    code_context: str = ""


class DiffFile(BaseModel):
    path: str
    added_lines: list[tuple[int, str]]
    removed_lines: list[tuple[int, str]]
    hunks: list[dict]
    full_new_content: Optional[str] = None
    language: str = "unknown"


class CodeChunk(BaseModel):
    file_path: str
    code: str
    start_line: int
    end_line: int
    chunk_type: str
    name: Optional[str] = None

"""Line comment logic (Notepad++ Edit > Comment/Uncomment), independent of Qt.

Languages with a line comment token (``#``, ``//``) use it; languages that
only have block comments (XML, HTML, CSS) wrap each line in the block pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommentMode(Enum):
    TOGGLE = "toggle"
    COMMENT = "comment"
    UNCOMMENT = "uncomment"


@dataclass(frozen=True)
class CommentStyle:
    line: str = ""
    block_start: str = ""
    block_end: str = ""

    @property
    def supported(self) -> bool:
        return bool(self.line or (self.block_start and self.block_end))


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def is_commented(line: str, style: CommentStyle) -> bool:
    body = line.lstrip(" \t")
    if style.line:
        return body.startswith(style.line)
    return body.startswith(style.block_start) and body.rstrip().endswith(style.block_end)


def _comment(line: str, column: int, style: CommentStyle) -> str:
    head, body = line[:column], line[column:]
    if style.line:
        return f"{head}{style.line} {body}"
    return f"{head}{style.block_start} {body} {style.block_end}"


def _uncomment(line: str, style: CommentStyle) -> str:
    column = _indent(line)
    head, body = line[:column], line[column:]
    if style.line:
        body = body[len(style.line) :]
        return head + (body[1:] if body.startswith(" ") else body)
    body = body[len(style.block_start) :]
    body = body[1:] if body.startswith(" ") else body
    stripped = body.rstrip()
    trailing = body[len(stripped) :]
    stripped = stripped[: -len(style.block_end)]
    stripped = stripped[:-1] if stripped.endswith(" ") else stripped
    return head + stripped + trailing


def apply_comment(lines: list[str], style: CommentStyle, mode: CommentMode) -> list[str]:
    """Return ``lines`` (without line endings) commented, uncommented or toggled.

    Toggle uncomments when every non-empty line is commented, otherwise it
    comments. Comments are inserted at the smallest indentation so a block
    stays aligned. Empty lines are left alone.
    """
    if not style.supported:
        return list(lines)
    content = [line for line in lines if line.strip()]
    if not content:
        return list(lines)
    if mode is CommentMode.TOGGLE:
        all_commented = all(is_commented(line, style) for line in content)
        mode = CommentMode.UNCOMMENT if all_commented else CommentMode.COMMENT
    if mode is CommentMode.COMMENT:
        column = min(_indent(line) for line in content)
        return [_comment(line, column, style) if line.strip() else line for line in lines]
    return [
        _uncomment(line, style) if line.strip() and is_commented(line, style) else line
        for line in lines
    ]

"""Regex tester logic (no Qt): matches with groups, replace preview, flags."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

# Flag letter, re flag, tooltip key (translated in the UI).
FLAGS = (
    ("i", re.IGNORECASE),
    ("m", re.MULTILINE),
    ("s", re.DOTALL),
    ("x", re.VERBOSE),
)
MAX_MATCHES = 1000


@dataclass(frozen=True)
class Group:
    name: str  # "1", "2" or the group's name
    start: int  # -1 when the group did not take part
    end: int
    text: str | None


@dataclass(frozen=True)
class Found:
    start: int
    end: int
    text: str
    groups: tuple[Group, ...]


@dataclass
class Result:
    matches: list[Found] = field(default_factory=list)
    error: str = ""
    error_position: int | None = None
    truncated: bool = False


def flag_value(letters: Iterable[str]) -> int:
    chosen = set(letters)
    value = 0
    for letter, flag in FLAGS:
        if letter in chosen:
            value |= flag
    return value


def compile_pattern(pattern: str, flags: int) -> re.Pattern[str]:
    return re.compile(pattern, flags)


def evaluate(pattern: str, flags: int, text: str, limit: int = MAX_MATCHES) -> Result:
    if not pattern:
        return Result()
    try:
        compiled = compile_pattern(pattern, flags)
    except re.error as error:
        return Result(error=error.msg, error_position=error.pos)
    result = Result()
    names = {index: name for name, index in compiled.groupindex.items()}
    for match in compiled.finditer(text):
        if len(result.matches) >= limit:
            result.truncated = True
            break
        groups = tuple(
            Group(
                names.get(index, str(index)),
                match.start(index),
                match.end(index),
                match.group(index),
            )
            for index in range(1, compiled.groups + 1)
        )
        result.matches.append(Found(match.start(), match.end(), match.group(0), groups))
    return result


def replace(pattern: str, flags: int, text: str, replacement: str) -> tuple[str, int] | str:
    """(new text, count), or an error message."""
    try:
        return compile_pattern(pattern, flags).subn(replacement, text)
    except (re.error, IndexError) as error:
        return str(error)


def python_literal(pattern: str, flags: int) -> str:
    """The pattern as Python code: re.compile(r"...", re.I | ...)."""
    if '"' not in pattern and not pattern.endswith("\\"):
        literal = f'r"{pattern}"'
    elif "'" not in pattern and not pattern.endswith("\\"):
        literal = f"r'{pattern}'"
    else:
        literal = repr(pattern)
    names = [f"re.{flag.name}" for _letter, flag in FLAGS if flags & flag]
    return f"re.compile({literal}{', ' + ' | '.join(names) if names else ''})"


def byte_offsets(text: str, offsets: Iterable[int]) -> dict[int, int]:
    """UTF-8 byte position of each character offset (for Scintilla)."""
    result: dict[int, int] = {}
    position = 0
    previous = 0
    for offset in sorted(set(offsets)):
        position += len(text[previous:offset].encode("utf-8"))
        previous = offset
        result[offset] = position
    return result

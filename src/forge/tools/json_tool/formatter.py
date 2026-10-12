"""Token based JSON (re)formatting.

The text is validated with the json module, but formatted by walking its
tokens, so numbers ("1.50", "1e10"), string escapes and key order stay
exactly as written. Parsing into Python objects and dumping again would
silently change them.
"""

from __future__ import annotations

import json

_WHITESPACE = " \t\r\n"


class JsonError(ValueError):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


def validate(text: str) -> None:
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise JsonError(exc.msg, exc.lineno, exc.colno) from exc


def reformat(text: str, indent: str | None, eol: str = "\n") -> str:
    """Pretty print with ``indent`` per level, or minify when ``indent`` is None.

    Raises JsonError for invalid input.
    """
    validate(text)
    out: list[str] = []
    level = 0
    i = 0
    n = len(text)
    pretty = indent is not None
    unit = indent or ""

    def newline(depth: int) -> None:
        if pretty:
            out.append(eol + unit * depth)

    while i < n:
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            out.append(text[i : j + 1])
            i = j + 1
            continue
        if ch in _WHITESPACE:
            i += 1
            continue
        if ch in "{[":
            close = "}" if ch == "{" else "]"
            j = i + 1
            while j < n and text[j] in _WHITESPACE:
                j += 1
            if j < n and text[j] == close:
                out.append(ch + close)  # empty object or array stays on one line
                i = j + 1
                continue
            out.append(ch)
            level += 1
            newline(level)
        elif ch in "}]":
            level -= 1
            newline(level)
            out.append(ch)
        elif ch == ",":
            out.append(ch)
            newline(level)
        elif ch == ":":
            out.append(": " if pretty else ":")
        else:
            out.append(ch)
        i += 1
    return "".join(out)

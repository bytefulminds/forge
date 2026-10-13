"""Find where a value sits in JSON text (no Qt), for jumping from the tree
view to the code. A path is a tuple of object keys (str) and array indexes (int)."""

from __future__ import annotations

Path = tuple[str | int, ...]

_WHITESPACE = " \t\r\n"


class _Found(Exception):
    def __init__(self, offset: int) -> None:
        self.offset = offset


class _Scanner:
    def __init__(self, text: str, target: Path) -> None:
        self.text = text
        self.target = target
        self.i = 0

    def skip(self) -> None:
        text, i = self.text, self.i
        while i < len(text) and text[i] in _WHITESPACE:
            i += 1
        self.i = i

    def string(self) -> str:
        """Read a string literal at ``self.i`` and return its raw content."""
        text, start = self.text, self.i + 1
        i = start
        while i < len(text):
            char = text[i]
            if char == "\\":
                i += 2
                continue
            if char == '"':
                self.i = i + 1
                return _unescape(text[start:i])
            i += 1
        raise ValueError("unterminated string")

    def value(self, path: Path) -> None:
        self.skip()
        if self.i >= len(self.text):
            raise ValueError("unexpected end")
        char = self.text[self.i]
        if char == "{":
            self.obj(path)
        elif char == "[":
            self.array(path)
        elif char == '"':
            self.string()
        else:  # number, true, false, null
            text, i = self.text, self.i
            while i < len(text) and text[i] not in ",]}" + _WHITESPACE:
                i += 1
            self.i = i

    def obj(self, path: Path) -> None:
        self.i += 1
        while True:
            self.skip()
            if self.text[self.i] == "}":
                self.i += 1
                return
            key_offset = self.i
            key = self.string()
            child = (*path, key)
            if child == self.target:
                raise _Found(key_offset)
            self.skip()
            self.i += 1  # ":"
            self.value(child)
            self.skip()
            if self.text[self.i] == ",":
                self.i += 1

    def array(self, path: Path) -> None:
        self.i += 1
        index = 0
        while True:
            self.skip()
            if self.text[self.i] == "]":
                self.i += 1
                return
            child = (*path, index)
            if child == self.target:
                raise _Found(self.i)
            self.value(child)
            index += 1
            self.skip()
            if self.text[self.i] == ",":
                self.i += 1


def _unescape(raw: str) -> str:
    if "\\" not in raw:
        return raw
    import json

    try:
        value = json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw
    return value if isinstance(value, str) else raw


def find_offset(text: str, path: Path) -> int | None:
    """Character offset of the key (in an object) or the value (in an array)
    at ``path``; the start of the document for the root; ``None`` if absent."""
    scanner = _Scanner(text, path)
    if not path:
        scanner.skip()
        return scanner.i
    try:
        scanner.value(())
    except _Found as found:
        return found.offset
    except (ValueError, IndexError):
        return None
    return None


def line_and_column(text: str, offset: int) -> tuple[int, int]:
    """0-based line and character column of ``offset``."""
    line = text.count("\n", 0, offset)
    start = text.rfind("\n", 0, offset) + 1
    return line, offset - start

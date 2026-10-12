from __future__ import annotations

import pytest

from forge.core.eol import Eol, convert_eol, detect_eol


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a\nb\nc", Eol.LF),
        ("a\r\nb\r\nc", Eol.CRLF),
        ("a\rb\rc", Eol.CR),
        ("no line endings", Eol.LF),
        ("a\r\nb\r\nc\nd", Eol.CRLF),
    ],
)
def test_detect_eol(text: str, expected: Eol) -> None:
    assert detect_eol(text) is expected


def test_convert_eol() -> None:
    mixed = "a\r\nb\rc\nd"
    assert convert_eol(mixed, Eol.LF) == "a\nb\nc\nd"
    assert convert_eol(mixed, Eol.CRLF) == "a\r\nb\r\nc\r\nd"
    assert convert_eol(mixed, Eol.CR) == "a\rb\rc\rd"

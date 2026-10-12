from __future__ import annotations

from forge.core.encoding import CP1252, UTF8, TextEncoding, can_encode, reinterpret


def test_reinterpret_skips_matching_bom() -> None:
    data = b"\xef\xbb\xbfcaf\xc3\xa9"
    assert reinterpret(data, TextEncoding(UTF8)) == "café"


def test_reinterpret_as_cp1252() -> None:
    assert reinterpret(b"caf\xe9", TextEncoding(CP1252)) == "café"


def test_can_encode() -> None:
    assert can_encode("café", TextEncoding(CP1252))
    assert not can_encode("emoji 🙂", TextEncoding(CP1252))

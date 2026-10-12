from __future__ import annotations

import codecs

import pytest

from forge.core.encoding import (
    CP1252,
    UTF8,
    UTF16_BE,
    UTF16_LE,
    TextEncoding,
    decode,
    detect_encoding,
    encode,
)

SAMPLE = "Héllo wörld, € 10\n"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (SAMPLE.encode("utf-8"), TextEncoding(UTF8)),
        (codecs.BOM_UTF8 + SAMPLE.encode("utf-8"), TextEncoding(UTF8, bom=True)),
        (codecs.BOM_UTF16_LE + SAMPLE.encode("utf-16-le"), TextEncoding(UTF16_LE, bom=True)),
        (codecs.BOM_UTF16_BE + SAMPLE.encode("utf-16-be"), TextEncoding(UTF16_BE, bom=True)),
        (b"plain ascii\n", TextEncoding(UTF8)),
        (b"", TextEncoding(UTF8)),
    ],
)
def test_detect_encoding(data: bytes, expected: TextEncoding) -> None:
    assert detect_encoding(data) == expected


def test_non_utf8_bytes_are_decodable() -> None:
    data = ("Café crème brûlée, naïve " * 20).encode(CP1252)
    encoding = detect_encoding(data)
    assert encoding.codec != UTF8
    assert "Caf" in decode(data, encoding)


@pytest.mark.parametrize(
    "encoding",
    [
        TextEncoding(UTF8),
        TextEncoding(UTF8, bom=True),
        TextEncoding(UTF16_LE, bom=True),
        TextEncoding(UTF16_BE, bom=True),
    ],
)
def test_round_trip(encoding: TextEncoding) -> None:
    assert decode(encode(SAMPLE, encoding), encoding) == SAMPLE


def test_labels() -> None:
    assert TextEncoding(UTF8).label == "UTF-8"
    assert TextEncoding(UTF8, bom=True).label == "UTF-8 BOM"
    assert TextEncoding(UTF16_LE, bom=True).label == "UTF-16 LE"

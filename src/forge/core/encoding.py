"""Text encoding detection, decoding and encoding.

Detection order: byte order mark, strict UTF-8, charset-normalizer guess,
and finally Windows-1252 which can decode any byte sequence we care about.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass

from charset_normalizer import from_bytes

UTF8 = "utf-8"
UTF16_LE = "utf-16-le"
UTF16_BE = "utf-16-be"
LATIN1 = "latin-1"
CP1252 = "cp1252"

_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, UTF8),
    (codecs.BOM_UTF16_LE, UTF16_LE),
    (codecs.BOM_UTF16_BE, UTF16_BE),
)

# Display names shown in the status bar, Notepad++ style.
_LABELS = {
    UTF8: "UTF-8",
    UTF16_LE: "UTF-16 LE",
    UTF16_BE: "UTF-16 BE",
    LATIN1: "ISO-8859-1",
    CP1252: "Windows-1252",
}


@dataclass(frozen=True)
class TextEncoding:
    codec: str = UTF8
    bom: bool = False

    @property
    def label(self) -> str:
        name = _LABELS.get(self.codec, self.codec.upper())
        return f"{name} BOM" if self.bom and self.codec == UTF8 else name

    def bom_bytes(self) -> bytes:
        if not self.bom:
            return b""
        for bom, codec in _BOMS:
            if codec == self.codec:
                return bom
        return b""


DEFAULT_ENCODING = TextEncoding()


def detect_encoding(data: bytes) -> TextEncoding:
    for bom, codec in _BOMS:
        if data.startswith(bom):
            return TextEncoding(codec, bom=True)
    try:
        data.decode(UTF8)
    except UnicodeDecodeError:
        pass
    else:
        return DEFAULT_ENCODING
    best = from_bytes(data[:256_000]).best()
    if best is not None:
        codec = codecs.lookup(best.encoding).name
        try:
            data.decode(codec)
        except (UnicodeDecodeError, LookupError):
            pass
        else:
            return TextEncoding(codec)
    return TextEncoding(CP1252 if _decodes(data, CP1252) else LATIN1)


def _decodes(data: bytes, codec: str) -> bool:
    try:
        data.decode(codec)
    except UnicodeDecodeError:
        return False
    return True


def decode(data: bytes, encoding: TextEncoding) -> str:
    payload = data[len(encoding.bom_bytes()) :] if encoding.bom else data
    return payload.decode(encoding.codec)


def encode(text: str, encoding: TextEncoding) -> bytes:
    return encoding.bom_bytes() + text.encode(encoding.codec)

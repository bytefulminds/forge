"""Line ending detection and conversion."""

from __future__ import annotations

from enum import Enum


class Eol(Enum):
    LF = "\n"
    CRLF = "\r\n"
    CR = "\r"

    @property
    def label(self) -> str:
        return {"LF": "Unix (LF)", "CRLF": "Windows (CR LF)", "CR": "Macintosh (CR)"}[self.name]


DEFAULT_EOL = Eol.LF


def detect_eol(text: str, sample_size: int = 1_000_000) -> Eol:
    """Return the most common line ending in the first ``sample_size`` characters."""
    sample = text[:sample_size]
    crlf = sample.count("\r\n")
    lf = sample.count("\n") - crlf
    cr = sample.count("\r") - crlf
    if crlf == lf == cr == 0:
        return DEFAULT_EOL
    counts = {Eol.CRLF: crlf, Eol.LF: lf, Eol.CR: cr}
    return max(counts, key=lambda eol: counts[eol])


def convert_eol(text: str, eol: Eol) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if eol is Eol.LF else normalized.replace("\n", eol.value)

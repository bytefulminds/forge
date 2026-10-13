"""Unix timestamps and ISO 8601 dates (no Qt): used by the CSV and date tools."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

_EPOCH = re.compile(r"^-?\d{9,19}(\.\d+)?$")
_EPOCH_IN_TEXT = re.compile(r"(?<![\d.])\d{10}(?:\d{3}|\d{6}|\d{9})?(?:\.\d+)?(?![\d.])")
_ISO_IN_TEXT = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_EPOCH_START = datetime(1970, 1, 1, tzinfo=UTC)


def epoch_to_iso(value: str, local: bool = False) -> str | None:
    """Unix time in seconds, milliseconds, microseconds or nanoseconds
    (picked from the number of digits) as ISO 8601; ``None`` if not a timestamp."""
    text = value.strip()
    if not _EPOCH.match(text):
        return None
    digits = len(text.split(".")[0].lstrip("-"))
    scale = {10: 1, 13: 1_000, 16: 1_000_000, 19: 1_000_000_000}.get(digits)
    if scale is None:
        if digits != 9:
            return None
        scale = 1  # 1973 to 2001 in seconds
    integer, _, fraction = text.partition(".")
    micros = int(integer) * 1_000_000 // scale
    if fraction and scale == 1:
        micros += int((fraction + "000000")[:6]) * (-1 if text.startswith("-") else 1)
    try:
        moment = _EPOCH_START + timedelta(microseconds=micros)
    except OverflowError:
        return None
    if local:
        moment = moment.astimezone()
    if micros % 1_000_000 == 0:
        spec = "seconds"
    elif micros % 1_000 == 0:
        spec = "milliseconds"
    else:
        spec = "microseconds"
    iso = moment.isoformat(timespec=spec)
    return iso.replace("+00:00", "Z") if not local else iso


def iso_to_epoch(value: str, milliseconds: bool = False) -> str | None:
    """ISO 8601 date-time as Unix time (seconds, or milliseconds); text
    without a time zone is read as UTC. ``None`` if it is not a date-time."""
    text = value.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        moment = datetime.fromisoformat(text.replace(" ", "T", 1))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    delta = moment - _EPOCH_START
    micros = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    if milliseconds:
        return str(micros // 1_000)
    if micros % 1_000_000 == 0:
        return str(micros // 1_000_000)
    return f"{micros / 1_000_000:.6f}".rstrip("0")


def convert_in_text(
    text: str, to_iso: bool, local: bool = False, milliseconds: bool = False
) -> tuple[str, int]:
    """Convert every timestamp found in free text (used for selections)."""
    count = 0

    def epoch(match: re.Match[str]) -> str:
        nonlocal count
        result = epoch_to_iso(match.group(0), local)
        if result is None:
            return match.group(0)
        count += 1
        return result

    def iso(match: re.Match[str]) -> str:
        nonlocal count
        result = iso_to_epoch(match.group(0), milliseconds)
        if result is None:
            return match.group(0)
        count += 1
        return result

    if to_iso:
        return _EPOCH_IN_TEXT.sub(epoch, text), count
    return _ISO_IN_TEXT.sub(iso, text), count

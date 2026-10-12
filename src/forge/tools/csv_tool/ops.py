"""CSV transformations on raw records (no Qt). Fields keep their original
quoting unless a value changes, so untouched cells stay byte-for-byte equal."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from forge.core.csvtext import Record, is_quoted, quote, unquote

_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_DECIMAL_COMMA = re.compile(r"^[+-]?\d+,\d+$")
_JSON_INT = re.compile(r"^-?(0|[1-9]\d*)$")
_JSON_FLOAT = re.compile(r"^-?(0|[1-9]\d*)\.\d+([eE][+-]?\d+)?$")
_EPOCH = re.compile(r"^-?\d{9,19}(\.\d+)?$")
_EPOCH_IN_TEXT = re.compile(r"(?<![\d.])\d{10}(?:\d{3}|\d{6}|\d{9})?(?:\.\d+)?(?![\d.])")
_ISO_IN_TEXT = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_EPOCH_START = datetime(1970, 1, 1, tzinfo=UTC)


# Header ---------------------------------------------------------------------------


def has_header(records: list[Record], delimiter: str) -> bool:
    """Whether the first record looks like column names: no numbers or dates in
    it, and its names do not come back as values in their own column."""
    rows = [r.values() for r in records[:200] if not r.is_blank]
    if len(rows) < 2:
        return True
    first, body = [v.strip() for v in rows[0]], rows[1:]
    if any(_NUMBER.match(value) or iso_to_epoch(value) for value in first if value):
        return False
    for column in range(len(first)):
        values = [row[column].strip() for row in body if column < len(row)]
        numbers = sum(1 for v in values if _NUMBER.match(v))
        if values and numbers / len(values) > 0.5:
            return True  # a text name above a numeric column
    return not any(
        row[column].strip() == name
        for row in body
        for column, name in enumerate(first)
        if column < len(row)
    )


def _split_header(records: list[Record], header: bool) -> tuple[list[Record], list[Record]]:
    return (records[:1], records[1:]) if header and records else ([], records)


# Layout ---------------------------------------------------------------------------


def align(records: list[Record]) -> list[Record]:
    """Pad cells with spaces so every column lines up (multi-line records and
    the last column are left alone)."""
    plain = [r for r in records if not any("\n" in f or "\r" in f for f in r.fields)]
    plain_ids = {id(r) for r in plain}
    widths: dict[int, int] = {}
    for record in plain:
        for i, field in enumerate(record.fields[:-1]):
            widths[i] = max(widths.get(i, 0), len(field.strip()))
    result = []
    for record in records:
        if id(record) not in plain_ids or record.is_blank:
            result.append(record)
            continue
        fields = [f.strip().ljust(widths[i]) for i, f in enumerate(record.fields[:-1])]
        fields.append(record.fields[-1].strip())
        result.append(Record(fields, record.end))
    return result


def shrink(records: list[Record]) -> list[Record]:
    """Remove spaces around cells (undoes Align)."""
    return [Record([f.strip() for f in r.fields], r.end) for r in records]


# Rows -----------------------------------------------------------------------------


def _with_ends(original: list[Record], reordered: list[Record]) -> list[Record]:
    """Give reordered records the line endings of the original positions, so
    the last line keeps (or keeps lacking) its final line break."""
    return [Record(r.fields, o.end) for r, o in zip(reordered, original, strict=True)]


def _sort_key(value: str) -> tuple[int, float, str]:
    text = value.strip()
    if _DECIMAL_COMMA.match(text):
        text = text.replace(",", ".")  # 3,5 in Dutch (and many other) files
    if _NUMBER.match(text):
        return (0, float(text), "")
    return (1, 0.0, text.casefold())


def sort_rows(records: list[Record], column: int, descending: bool, header: bool) -> list[Record]:
    """Sort data rows by ``column`` (numbers numerically, text without case);
    blank lines move to the end and the header stays on top."""
    head, body = _split_header(records, header)
    rows = [r for r in body if not r.is_blank]
    blanks = [r for r in body if r.is_blank]

    def key(record: Record) -> tuple[int, float, str]:
        values = record.values()
        return _sort_key(values[column] if column < len(values) else "")

    ordered = sorted(rows, key=key, reverse=descending)
    return head + _with_ends(body, ordered + blanks)


def remove_duplicates(records: list[Record], header: bool) -> tuple[list[Record], int]:
    """Drop rows whose values equal an earlier row; returns the rows and the count."""
    head, body = _split_header(records, header)
    seen: set[tuple[str, ...]] = set()
    kept: list[Record] = []
    for record in body:
        if record.is_blank:
            kept.append(record)
            continue
        values = tuple(v.strip() for v in record.values())
        if values in seen:
            continue
        seen.add(values)
        kept.append(record)
    removed = len(body) - len(kept)
    if removed and kept and records and not records[-1].end:
        kept[-1] = Record(kept[-1].fields, "")
    return head + kept, removed


# Cells ----------------------------------------------------------------------------


def change_delimiter(records: list[Record], new: str) -> list[Record]:
    """Write the records with another delimiter, quoting cells that need it."""
    result = []
    for record in records:
        fields = [quote(unquote(f), new, force=is_quoted(f)) for f in record.fields]
        result.append(Record(fields, record.end))
    return result


def convert_column(
    records: list[Record],
    column: int,
    convert: Callable[[str], str | None],
    header: bool,
    delimiter: str,
) -> tuple[list[Record], int]:
    """Apply ``convert`` to every cell of ``column``; ``None`` keeps the cell."""
    head, body = _split_header(records, header)
    changed = 0
    result = list(head)
    for record in body:
        if column >= len(record.fields):
            result.append(record)
            continue
        field = record.fields[column]
        new = convert(unquote(field).strip())
        if new is None:
            result.append(record)
            continue
        fields = list(record.fields)
        fields[column] = quote(new, delimiter, force=is_quoted(field))
        result.append(Record(fields, record.end))
        changed += 1
    return result, changed


# Timestamps -----------------------------------------------------------------------


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


# Export ---------------------------------------------------------------------------


def _json_value(text: str) -> object:
    if _JSON_INT.match(text):
        return int(text)
    if _JSON_FLOAT.match(text):
        return float(text)
    if text in ("true", "false"):
        return text == "true"
    return text


def to_json(records: list[Record], header: bool, indent: str = "    ") -> str:
    """An array of objects (with a header) or of arrays; numbers become numbers."""
    rows = [r.values() for r in records if not r.is_blank]
    if header and rows:
        names = [name.strip() or f"column{i + 1}" for i, name in enumerate(rows[0])]
        data: list[object] = []
        for row in rows[1:]:
            item = {}
            for i, value in enumerate(row):
                name = names[i] if i < len(names) else f"column{i + 1}"
                item[name] = _json_value(value)
            data.append(item)
    else:
        data = [[_json_value(v) for v in row] for row in rows]
    return json.dumps(data, indent=indent, ensure_ascii=False) + "\n"


def to_markdown(records: list[Record], header: bool) -> str:
    rows = [[v.replace("|", "\\|").replace("\n", " ") for v in r.values()] for r in records]
    rows = [r for r, rec in zip(rows, records, strict=True) if not rec.is_blank]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    if header:
        head, body = rows[0], rows[1:]
    else:
        head, body = [str(i + 1) for i in range(width)], rows
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join([" --- "] * width) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines) + "\n"

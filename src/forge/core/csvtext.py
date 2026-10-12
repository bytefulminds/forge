"""CSV helpers shared by the CSV lexer and the table view (no Qt)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

CANDIDATE_DELIMITERS = (",", ";", "\t", "|")


def detect_delimiter(sample: str, default: str = ",") -> str:
    """Pick the delimiter that splits the first lines most consistently."""
    lines = [line for line in sample.splitlines()[:20] if line.strip()]
    if not lines:
        return default
    best, best_score = default, 0
    for delimiter in CANDIDATE_DELIMITERS:
        counts = [len(split_line(line, delimiter)) for line in lines]
        if min(counts) < 2:
            continue
        # Prefer delimiters that give the same column count on every line.
        consistency = counts.count(counts[0]) / len(counts)
        score = consistency * 1000 + counts[0]
        if score > best_score:
            best, best_score = delimiter, int(score)
    return best


def split_line(line: str, delimiter: str) -> list[str]:
    """Fields of one line, honoring double quotes (quotes are kept)."""
    fields: list[str] = []
    current: list[str] = []
    quoted = False
    for char in line:
        if char == '"':
            quoted = not quoted
            current.append(char)
        elif char == delimiter and not quoted:
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def read_rows(text: str, delimiter: str) -> list[list[str]]:
    """Parse ``text`` into rows (quotes removed, multi-line fields supported)."""
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


DELIMITER_NAMES = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}


class Record:
    """One CSV record as written in the file: raw fields (quotes kept) and the
    line ending that follows it. Joining records gives back the exact text."""

    __slots__ = ("end", "fields")

    def __init__(self, fields: list[str], end: str) -> None:
        self.fields = fields
        self.end = end

    @property
    def is_blank(self) -> bool:
        return len(self.fields) == 1 and not self.fields[0].strip()

    def values(self) -> list[str]:
        return [unquote(field) for field in self.fields]

    def __repr__(self) -> str:
        return f"Record({self.fields!r}, {self.end!r})"


def split_records(text: str, delimiter: str) -> list[Record]:
    """Split ``text`` into records; quoted fields may contain delimiters and
    line breaks. A final line ending does not start an extra record."""
    records: list[Record] = []
    fields: list[str] = []
    start = 0
    quoted = False
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char == delimiter:
                fields.append(text[start:i])
                start = i + 1
            elif char in "\r\n":
                end = "\r\n" if text.startswith("\r\n", i) else char
                fields.append(text[start:i])
                records.append(Record(fields, end))
                fields = []
                i += len(end)
                start = i
                continue
        i += 1
    if start < length or fields:
        fields.append(text[start:])
        records.append(Record(fields, ""))
    return records


def join_records(records: list[Record], delimiter: str) -> str:
    return "".join(delimiter.join(record.fields) + record.end for record in records)


def unquote(field: str) -> str:
    """The value of a raw field: surrounding quotes removed, "" becomes "."""
    stripped = field.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1].replace('""', '"')
    return field


def is_quoted(field: str) -> bool:
    stripped = field.strip()
    return len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"'


def quote(value: str, delimiter: str, force: bool = False) -> str:
    """A raw field for ``value``, quoted only when needed (or when forced)."""
    if force or any(c in value for c in (delimiter, '"', "\n", "\r")):
        return '"' + value.replace('"', '""') + '"'
    return value


def column_at(text_before_caret: str, delimiter: str) -> int:
    """0-based column of the caret, given the text from the start of the
    document (or of the record) up to the caret."""
    records = split_records(text_before_caret, delimiter)
    if not records or records[-1].end:
        return 0
    return len(records[-1].fields) - 1


@dataclass(frozen=True)
class CsvProblem:
    line: int  # 1-based line where the record starts
    kind: str  # "quote": unclosed quote; "columns": unexpected field count
    expected: int = 0
    found: int = 0


def find_problem(text: str, delimiter: str) -> CsvProblem | None:
    """The first structural problem: an unclosed quote, or a record whose
    field count differs from the first record (blank lines are ignored)."""
    line = 1
    expected: int | None = None
    for record in split_records(text, delimiter):
        raw = delimiter.join(record.fields)
        if raw.count('"') % 2 and not record.end:
            return CsvProblem(line, "quote")
        if not record.is_blank:
            if expected is None:
                expected = len(record.fields)
            elif len(record.fields) != expected:
                return CsvProblem(line, "columns", expected, len(record.fields))
        breaks = raw.count("\n") + raw.count("\r") - raw.count("\r\n")
        line += breaks + (1 if record.end else 0)
    return None

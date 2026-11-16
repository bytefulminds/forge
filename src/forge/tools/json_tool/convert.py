"""JSON conversions and path queries (no Qt).

Sorting keys keeps numbers exactly as written ("1.50" stays "1.50"):
numbers are parsed into ``Number`` objects that remember their text.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from forge.core.jsonpos import Path, find_offset


class Number(str):
    """A JSON number kept as its original text."""


def _constant(name: str) -> Number:
    return Number(name)  # NaN, Infinity: not JSON, but keep what is there


def load_exact(text: str) -> Any:
    """Parse JSON keeping key order and number text. Raises json.JSONDecodeError."""
    return json.loads(text, parse_float=Number, parse_int=Number, parse_constant=_constant)


def dump(value: Any, indent: str | None, eol: str = "\n", level: int = 0) -> str:
    """Serialize like json.dumps, but with ``Number`` text kept and the line end chosen."""
    if isinstance(value, Number):
        return str(value)
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, (datetime, date, time)):
        return json.dumps(value.isoformat())
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [
            f"{json.dumps(str(key), ensure_ascii=False)}:{' ' if indent is not None else ''}"
            f"{dump(item, indent, eol, level + 1)}"
            for key, item in value.items()
        ]
        return _wrap("{", "}", items, indent, eol, level)
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        items = [dump(item, indent, eol, level + 1) for item in value]
        return _wrap("[", "]", items, indent, eol, level)
    if isinstance(value, bytes):
        return json.dumps(value.decode("utf-8", "replace"), ensure_ascii=False)
    return json.dumps(str(value), ensure_ascii=False)


def _wrap(
    open_: str, close: str, items: list[str], indent: str | None, eol: str, level: int
) -> str:
    if indent is None:
        return open_ + ",".join(items) + close
    inner = eol + indent * (level + 1)
    return open_ + inner + ("," + inner).join(items) + eol + indent * level + close


def sort_keys(value: Any) -> Any:
    """Sort object keys at every level (case-insensitive, then exact)."""
    if isinstance(value, dict):
        return {
            key: sort_keys(value[key]) for key in sorted(value, key=lambda k: (k.casefold(), k))
        }
    if isinstance(value, list):
        return [sort_keys(item) for item in value]
    return value


def sorted_json(text: str, indent: str, eol: str = "\n") -> str:
    return dump(sort_keys(load_exact(text)), indent, eol)


# CSV ----------------------------------------------------------------------


class ConvertError(ValueError):
    pass


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return dump(value, None)
    return str(value)


def _flatten(value: Any, prefix: str, out: dict[str, Any]) -> None:
    """Nested objects become dotted columns ("address.city"); arrays stay JSON."""
    if isinstance(value, dict) and value:
        for key, item in value.items():
            _flatten(item, f"{prefix}.{key}" if prefix else str(key), out)
    else:
        out[prefix or "value"] = value


def to_csv(text: str, delimiter: str = ",", eol: str = "\n") -> str:
    """An array of objects (or one object) as CSV with a header row.

    Columns are the union of all keys in order of first appearance. An array
    of arrays becomes rows as is; an array of plain values one column.
    """
    data = load_exact(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ConvertError("not an array or object")
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator=eol)
    if data and all(isinstance(row, list) for row in data):
        for cells in data:
            writer.writerow([_cell(cell) for cell in cells])
        return buffer.getvalue()
    rows: list[dict[str, Any]] = []
    for item in data:
        row: dict[str, Any] = {}
        _flatten(item, "", row)
        rows.append(row)
    columns: dict[str, None] = {}
    for row in rows:
        columns.update(dict.fromkeys(row))
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(row.get(column)) for column in columns])
    return buffer.getvalue()


# YAML ---------------------------------------------------------------------


def _plain(value: Any) -> Any:
    """``Number`` text back to int or float for YAML."""
    if isinstance(value, Number):
        try:
            return int(value)
        except ValueError:
            return float(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def to_yaml(text: str, indent: int = 2) -> str:
    import yaml

    data = _plain(load_exact(text))
    result: str = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        indent=indent,
        width=4096,
    )
    return result


def yaml_to_json(text: str, indent: str, eol: str = "\n") -> str:
    """YAML as JSON; several documents become an array. Raises yaml.YAMLError."""
    import yaml

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    documents = list(yaml.load_all(text, Loader=loader))
    data: Any = documents[0] if len(documents) == 1 else documents
    return dump(data, indent, eol)


# Path query ---------------------------------------------------------------


class QueryError(ValueError):
    pass


@dataclass(frozen=True)
class _Step:
    kind: str  # "key", "index", "wild", "deep"
    value: str | int = ""


_TOKEN = re.compile(
    r"""
    \.\.(?P<deep>[A-Za-z_$][\w$-]*|\*)         # ..name or ..*
  | \.(?P<key>[A-Za-z_$][\w$-]*|\*)            # .name or .*
  | \[\s*(?P<index>-?\d+)\s*\]                 # [0]
  | \[\s*\*\s*\]                               # [*]
  | \[\s*(?P<quote>["'])(?P<qkey>(?:\\.|(?!(?P=quote)).)*)(?P=quote)\s*\]   # ['key']
    """,
    re.VERBOSE,
)


def parse_query(query: str) -> list[_Step]:
    """Parse ``$.a.b[0]``, ``a.b``, ``$['a b'][*]``, ``$..name``."""
    text = query.strip()
    if text.startswith("$"):
        text = text[1:]
    elif text and not text.startswith((".", "[")):
        text = "." + text
    steps: list[_Step] = []
    position = 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            raise QueryError(f"unexpected {text[position : position + 12]!r}")
        position = match.end()
        if match.group("deep") is not None:
            name = match.group("deep")
            steps.append(_Step("deep", "*" if name == "*" else name))
        elif match.group("key") is not None:
            name = match.group("key")
            steps.append(_Step("wild") if name == "*" else _Step("key", name))
        elif match.group("index") is not None:
            steps.append(_Step("index", int(match.group("index"))))
        elif match.group("qkey") is not None:
            raw = match.group("qkey")
            steps.append(_Step("key", re.sub(r"\\(.)", r"\1", raw)))
        else:
            steps.append(_Step("wild"))
    return steps


def _children(value: Any, path: Path) -> Iterator[tuple[Path, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield (*path, key), item
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield (*path, index), item


def _descendants(value: Any, path: Path) -> Iterator[tuple[Path, Any]]:
    for child_path, child in _children(value, path):
        yield child_path, child
        yield from _descendants(child, child_path)


def query_paths(data: Any, query: str) -> list[tuple[Path, Any]]:
    """Every (path, value) that ``query`` matches, in document order."""
    current: list[tuple[Path, Any]] = [((), data)]
    for step in parse_query(query):
        found: list[tuple[Path, Any]] = []
        for path, value in current:
            if step.kind == "key":
                if isinstance(value, dict) and step.value in value:
                    found.append(((*path, step.value), value[step.value]))
            elif step.kind == "index":
                if isinstance(value, list) and isinstance(step.value, int):
                    index = step.value + len(value) if step.value < 0 else step.value
                    if 0 <= index < len(value):
                        found.append(((*path, index), value[index]))
            elif step.kind == "wild":
                found.extend(_children(value, path))
            else:  # deep
                for child_path, child in _descendants(value, path):
                    if step.value == "*" or child_path[-1] == step.value:
                        found.append((child_path, child))
        unique: dict[Path, Any] = {}
        for path, value in found:
            unique.setdefault(path, value)
        current = list(unique.items())
    return current


@dataclass(frozen=True)
class Match:
    path: Path
    start: int  # character offset of the value
    end: int
    preview: str


def _value_end(text: str, start: int) -> int:
    """End offset of the JSON value that starts at ``start``."""
    decoder = json.JSONDecoder(parse_float=Number, parse_int=Number, parse_constant=_constant)
    _value, end = decoder.raw_decode(text, start)
    return int(end)


def _skip_to_value(text: str, offset: int, path: Path) -> int:
    """From a key's offset (object member) move to its value."""
    if not path or isinstance(path[-1], int):
        return offset
    i = offset + 1
    while i < len(text):  # end of the key string
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            break
        i += 1
    i = text.index(":", i + 1) + 1
    while text[i] in " \t\r\n":
        i += 1
    return i


def path_text(path: Path) -> str:
    out = "$"
    for part in path:
        if isinstance(part, int):
            out += f"[{part}]"
        elif re.fullmatch(r"[A-Za-z_$][\w$]*", part):
            out += f".{part}"
        else:
            out += "[" + json.dumps(part, ensure_ascii=False) + "]"
    return out


def query(text: str, expression: str, limit: int = 1000) -> list[Match]:
    """Matches of ``expression`` with their text ranges. Raises json.JSONDecodeError
    for invalid JSON and QueryError for a bad expression."""
    data = load_exact(text)
    matches: list[Match] = []
    for path, value in query_paths(data, expression)[:limit]:
        offset = find_offset(text, path)
        if offset is None:
            continue
        start = _skip_to_value(text, offset, path)
        end = _value_end(text, start)
        preview = dump(value, None)
        if len(preview) > 120:
            preview = preview[:117] + "..."
        matches.append(Match(path, start, end, preview))
    return matches

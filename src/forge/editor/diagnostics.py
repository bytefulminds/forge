"""Live syntax checks: the first error per document, shown as a red squiggle.

Each checker returns a Diagnostic with a 1-based line and column, or nothing.
Heavy parsers (yaml, lxml) are imported on first use.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from forge.core.csvtext import detect_delimiter, find_problem

# Larger documents are not checked while typing.
MAX_CHECKED_CHARS = 2_000_000


@dataclass(frozen=True)
class Diagnostic:
    line: int  # 1-based
    column: int  # 1-based, in characters
    message: str


def _json(text: str) -> Diagnostic | None:
    if not text.strip():
        return None
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return Diagnostic(exc.lineno, exc.colno, exc.msg)
    return None


def _yaml(text: str) -> Diagnostic | None:
    import yaml

    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    try:
        for _ in yaml.load_all(text, Loader=loader):
            pass
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        if mark is None:
            return Diagnostic(1, 1, str(exc))
        return Diagnostic(mark.line + 1, mark.column + 1, exc.problem or str(exc))
    except yaml.YAMLError as exc:
        return Diagnostic(1, 1, str(exc))
    return None


def _xml(text: str) -> Diagnostic | None:
    if not text.strip():
        return None
    from forge.core.xmlsafe import XmlError, parse

    try:
        parse(text)
    except XmlError as exc:
        return Diagnostic(max(1, exc.line), max(1, exc.column), exc.message)
    return None


def _python(text: str) -> Diagnostic | None:
    try:
        compile(text, "<forge>", "exec", dont_inherit=True)
    except SyntaxError as exc:
        return Diagnostic(exc.lineno or 1, exc.offset or 1, exc.msg)
    except ValueError as exc:  # e.g. null bytes
        return Diagnostic(1, 1, str(exc))
    return None


_TOML_POSITION = re.compile(r"\(at line (\d+), column (\d+)\)")


def _toml(text: str) -> Diagnostic | None:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        message = str(exc)
        match = _TOML_POSITION.search(message)
        if match is None:
            return Diagnostic(1, 1, message)
        clean = _TOML_POSITION.sub("", message).strip()
        return Diagnostic(int(match.group(1)), int(match.group(2)), clean)
    return None


_BY_LANGUAGE: dict[str, Callable[[str], Diagnostic | None]] = {
    "json": _json,
    "yaml": _yaml,
    "xml": _xml,
    "python": _python,
}


def checker_for(language_id: str, path: Path | None) -> Callable[[str], Diagnostic | None] | None:
    if path is not None and path.suffix.lower() == ".toml":
        return _toml
    return _BY_LANGUAGE.get(language_id)


def check(
    language_id: str, path: Path | None, text: str, delimiter: str | None = None
) -> Diagnostic | None:
    if len(text) > MAX_CHECKED_CHARS:
        return None
    if language_id == "csv":
        return _csv(text, delimiter or detect_delimiter(text[:20_000]))
    checker = checker_for(language_id, path)
    if checker is None:
        return None
    return checker(text)


def _csv(text: str, delimiter: str) -> Diagnostic | None:
    from forge.i18n.translator import tr

    problem = find_problem(text, delimiter)
    if problem is None:
        return None
    if problem.kind == "quote":
        return Diagnostic(problem.line, 1, tr("A quote is opened here but never closed."))
    return Diagnostic(
        problem.line,
        1,
        tr(
            "This row has {found} columns; the first row has {expected}.",
            found=problem.found,
            expected=problem.expected,
        ),
    )

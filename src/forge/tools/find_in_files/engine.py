"""Folder search and replace, independent of Qt (runs on a worker thread)."""

from __future__ import annotations

import fnmatch
import os
import re
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from forge.core.encoding import decode, detect_encoding
from forge.core.fileio import load_text, save_text

MAX_FILE_BYTES = 50_000_000
MAX_HITS = 20_000
BINARY_SNIFF_BYTES = 8192
# Folders nobody wants to search through by default.
DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
        ".mypy_cache", ".ruff_cache", ".pytest_cache", ".idea", ".tox",
    }
)  # fmt: skip


@dataclass(frozen=True)
class Query:
    pattern: str
    folder: Path
    match_case: bool = False
    whole_word: bool = False
    regex: bool = False
    include: tuple[str, ...] = ()  # e.g. ("*.py", "*.json"); empty means all files
    exclude: tuple[str, ...] = ()  # file or folder name patterns
    recursive: bool = True

    def compile(self) -> re.Pattern[str]:
        """Raises re.error for an invalid regular expression."""
        source = self.pattern if self.regex else re.escape(self.pattern)
        if self.whole_word:
            source = rf"\b(?:{source})\b"
        flags = re.MULTILINE | (0 if self.match_case else re.IGNORECASE)
        return re.compile(source, flags)


@dataclass(frozen=True)
class Hit:
    line: int  # 1-based
    column: int  # 1-based, in characters
    length: int
    text: str  # the whole line, for display


@dataclass
class FileResult:
    path: Path
    hits: list[Hit] = field(default_factory=list)


def parse_filters(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split "*.py *.json !build" into include and exclude patterns."""
    include: list[str] = []
    exclude: list[str] = []
    for token in text.replace(";", " ").replace(",", " ").split():
        if token.startswith("!") and len(token) > 1:
            exclude.append(token[1:])
        else:
            include.append(token)
    return tuple(include), tuple(exclude)


def _excluded(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def iter_files(query: Query, cancel: threading.Event) -> Iterator[Path]:
    for root, dirs, files in os.walk(query.folder):
        if cancel.is_set():
            return
        dirs[:] = sorted(
            d for d in dirs if d not in DEFAULT_EXCLUDED_DIRS and not _excluded(d, query.exclude)
        )
        if not query.recursive:
            dirs[:] = []
        for name in sorted(files):
            if _excluded(name, query.exclude):
                continue
            if query.include and not any(fnmatch.fnmatch(name, p) for p in query.include):
                continue
            yield Path(root) / name


def read_text(path: Path) -> str | None:
    """File content as text, or None for binary, huge or unreadable files."""
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:BINARY_SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return decode(data, detect_encoding(data))


def search_text(text: str, pattern: re.Pattern[str], limit: int) -> list[Hit]:
    hits: list[Hit] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in pattern.finditer(line):
            if match.end() == match.start():
                continue
            hits.append(Hit(number, match.start() + 1, match.end() - match.start(), line))
            if len(hits) >= limit:
                return hits
    return hits


@dataclass
class Summary:
    files_searched: int = 0
    files_matched: int = 0
    hits: int = 0
    truncated: bool = False
    cancelled: bool = False


def search(
    query: Query,
    cancel: threading.Event,
    on_result: Callable[[FileResult], None],
    on_progress: Callable[[int], None] | None = None,
) -> Summary:
    pattern = query.compile()
    summary = Summary()
    for path in iter_files(query, cancel):
        if cancel.is_set():
            summary.cancelled = True
            break
        summary.files_searched += 1
        if on_progress is not None and summary.files_searched % 200 == 0:
            on_progress(summary.files_searched)
        text = read_text(path)
        if text is None:
            continue
        hits = search_text(text, pattern, MAX_HITS - summary.hits)
        if hits:
            summary.files_matched += 1
            summary.hits += len(hits)
            on_result(FileResult(path, hits))
        if summary.hits >= MAX_HITS:
            summary.truncated = True
            break
    return summary


def replace_in_file(path: Path, pattern: re.Pattern[str], replacement: str, regex: bool) -> int:
    """Replace every match in ``path``, keeping its encoding and line endings."""
    loaded = load_text(path)
    if regex:
        new_text, count = pattern.subn(replacement, loaded.text)
    else:
        new_text, count = pattern.subn(lambda _m: replacement, loaded.text)
    if count:
        save_text(path, new_text, loaded.encoding)
    return count

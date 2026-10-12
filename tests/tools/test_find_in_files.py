from __future__ import annotations

import threading
from pathlib import Path

from forge.tools.find_in_files.engine import (
    FileResult,
    Query,
    parse_filters,
    replace_in_file,
    search,
)


def _tree(root: Path) -> None:
    (root / "src").mkdir()
    (root / "node_modules").mkdir()
    (root / "src" / "a.py").write_text("token = 1\nTOKEN = 2\n")
    (root / "src" / "b.json").write_text('{"token": true}\n')
    (root / "node_modules" / "c.py").write_text("token\n")
    (root / "image.bin").write_bytes(b"token\0\0\0")
    (root / "latin.txt").write_bytes("café token\r\n".encode("cp1252"))


def _run(query: Query) -> list[FileResult]:
    results: list[FileResult] = []
    search(query, threading.Event(), results.append)
    return results


def test_search_skips_binary_and_default_folders(tmp_path: Path) -> None:
    _tree(tmp_path)
    results = _run(Query("token", tmp_path))
    names = sorted(r.path.name for r in results)
    assert names == ["a.py", "b.json", "latin.txt"]
    a = next(r for r in results if r.path.name == "a.py")
    assert [(h.line, h.column) for h in a.hits] == [(1, 1), (2, 1)]


def test_filters_case_and_whole_word(tmp_path: Path) -> None:
    _tree(tmp_path)
    include, exclude = parse_filters("*.py *.txt !latin.txt")
    results = _run(Query("TOKEN", tmp_path, match_case=True, include=include, exclude=exclude))
    assert [(r.path.name, len(r.hits)) for r in results] == [("a.py", 1)]


def test_replace_keeps_encoding_and_line_endings(tmp_path: Path) -> None:
    _tree(tmp_path)
    file = tmp_path / "latin.txt"
    pattern = Query("token", tmp_path).compile()
    assert replace_in_file(file, pattern, "jeton", regex=False) == 1
    assert file.read_bytes() == "café jeton\r\n".encode("cp1252")


def test_regex_replacement_groups(tmp_path: Path) -> None:
    file = tmp_path / "x.txt"
    file.write_text("a=1\nb=2\n")
    pattern = Query(r"(\w)=(\d)", tmp_path, regex=True).compile()
    assert replace_in_file(file, pattern, r"\2=\1", regex=True) == 2
    assert file.read_text() == "1=a\n2=b\n"

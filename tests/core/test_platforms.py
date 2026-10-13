"""Platform specific choices, tested for every platform on any machine."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.core import fileio
from forge.core.encoding import TextEncoding
from forge.core.eol import Eol, default_eol


def test_new_documents_use_the_platform_line_ending() -> None:
    assert default_eol("win32") is Eol.CRLF
    assert default_eol("darwin") is Eol.LF
    assert default_eol("linux") is Eol.LF


def test_reveal_selects_the_file_in_finder_and_explorer() -> None:
    from forge.ui.main_window import reveal_command

    path = Path("/some folder/notes.md")
    assert reveal_command(path, "darwin") == ["open", "-R", str(path)]
    assert reveal_command(path, "win32") == f'explorer /select,"{path}"'
    assert reveal_command(path, "linux") is None


def test_save_retries_while_windows_locks_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "a.txt"
    target.write_text("old", newline="")
    real_replace = fileio.os.replace
    calls = {"n": 0}

    def busy_twice(src: object, dst: object) -> None:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("in use")
        real_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(fileio.os, "replace", busy_twice)
    monkeypatch.setattr(fileio, "_REPLACE_WAIT_SECONDS", 0)
    fileio.save_text(target, "new", TextEncoding("utf-8"))
    assert target.read_text() == "new" and calls["n"] == 3
    assert not list(tmp_path.glob("*.forge-tmp"))

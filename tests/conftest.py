"""Shared test setup: headless Qt and an isolated Forge home directory."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Must be set before Qt is imported anywhere.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The rich Markdown preview (Qt WebEngine) has its own tests; the others use
# the basic preview so they stay fast and need no browser engine.
os.environ.setdefault("FORGE_BASIC_MARKDOWN", "1")

from PyQt6.QtCore import QCoreApplication, Qt

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)


@pytest.fixture(autouse=True)
def same_on_every_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    """New documents use LF in tests, also on Windows (where Forge uses CR LF),
    so expected texts are the same everywhere. tests/core/test_platforms.py
    checks the real platform defaults."""
    from forge.core import document, eol

    monkeypatch.setattr(document, "DEFAULT_EOL", eol.Eol.LF)
    monkeypatch.setattr(eol, "DEFAULT_EOL", eol.Eol.LF)


@pytest.fixture(autouse=True)
def no_blocking_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Headless, nobody can click a dialog away: a dialog or popup menu a test
    did not patch would wait forever. Fail at once instead, with its title."""
    from PyQt6.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox

    def refuse(self: QDialog | QMenu, *_args: object, **_kwargs: object) -> int:
        raise AssertionError(
            f"A test opened a {type(self).__name__} ({self.windowTitle()!r}) without "
            "patching it; it would block the headless test run."
        )

    def refuse_static(*args: object, **_kwargs: object) -> object:
        title = next((a for a in args if isinstance(a, str)), "")
        raise AssertionError(f"A test opened a native dialog ({title!r}) without patching it.")

    monkeypatch.setattr(QDialog, "exec", refuse)
    monkeypatch.setattr(QMenu, "exec", refuse)
    for name in ("question", "warning", "information", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, refuse_static)
    for name in ("getOpenFileNames", "getSaveFileName", "getExistingDirectory"):
        monkeypatch.setattr(QFileDialog, name, refuse_static)


@pytest.fixture(autouse=True)
def forge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    home = tmp_path / "forge-home"
    monkeypatch.setenv("FORGE_HOME", str(home))
    yield home

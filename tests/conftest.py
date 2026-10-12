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
def forge_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    home = tmp_path / "forge-home"
    monkeypatch.setenv("FORGE_HOME", str(home))
    yield home

"""The icon in front of the window title: unsaved, saved, or reloaded."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.ui import main_window as main_window_module
from forge.ui.main_window import MainWindow


def make_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def test_state_icon_follows_the_document(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = make_window(qtbot)
    bar = window.title_bar
    assert bar.status_kind is None  # empty new document
    assert "*" not in window.windowTitle()

    path = tmp_path / "notes.txt"
    path.write_text("one\n", newline="")
    tab = window.open_path(path)
    assert tab is not None
    qtbot.waitUntil(lambda: not tab.loading)
    assert bar.status_kind == "saved"

    tab.insert("zero ")
    assert bar.status_kind == "unsaved"
    assert bar.toolTip() == "Unsaved changes"
    assert "*" not in window.windowTitle()
    assert window.save(tab)
    assert bar.status_kind == "saved"

    path.write_text("changed elsewhere\n", newline="")
    window._on_changed_on_disk(path)
    qtbot.waitUntil(lambda: tab.text() == "changed elsewhere\n")
    assert bar.status_kind == "reloaded"
    assert bar.toolTip().startswith("Reloaded at")

    # The blue icon is temporary: after RELOADED_SECONDS it shows saved again.
    monkeypatch.setattr(main_window_module, "RELOADED_SECONDS", 0)
    window._state_expired()
    assert bar.status_kind == "saved"

    window._mark_reloaded(tab)
    tab.insert("x")  # editing makes the reload old news
    assert bar.status_kind == "unsaved" and tab.reloaded_at is None

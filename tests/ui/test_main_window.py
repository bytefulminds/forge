from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.ui.main_window import MainWindow


def make_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def test_starts_with_one_untitled_tab(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    assert window.tabs.count() == 1
    tab = window.current_tab()
    assert tab is not None
    assert tab.doc.display_name == "new 1"


def test_new_documents_get_increasing_names(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    window.new_document()
    window.new_document()
    names = [tab.doc.display_name for tab in window.all_tabs()]
    assert names == ["new 1", "new 2", "new 3"]


def test_open_replaces_pristine_untitled_tab(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "data.json"
    file.write_text('{"a": 1}\n')
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    assert window.tabs.count() == 1
    assert tab.text() == '{"a": 1}\n'
    assert tab.language.id == "json"
    assert not tab.is_dirty


def test_opening_same_file_twice_reuses_tab(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("x")
    window = make_window(qtbot)
    window.new_document().setText("keep me")
    first = window.open_path(file)
    second = window.open_path(file)
    assert first is second
    assert window.tabs.count() == 3  # new 1, new 2 (edited) and a.txt


def test_edit_and_save(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "notes.txt"
    file.write_text("one\r\n")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    tab.append("two\r\n")
    assert tab.is_dirty
    assert window.tabs.tabText(window.tabs.indexOf(tab)).endswith("●")
    assert window.save(tab)
    assert not tab.is_dirty
    assert file.read_bytes() == b"one\r\ntwo\r\n"


def test_close_dirty_tab_can_be_cancelled(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("unsaved")
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Cancel
    )
    assert not window.close_tab(tab)
    assert window.tabs.count() == 1

    monkeypatch.setattr(
        QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Discard
    )
    assert window.close_tab(tab)
    assert window.tabs.count() == 1  # a fresh "new 1" replaces the last tab


def test_theme_switch_is_saved(qtbot: QtBot, forge_home: Path) -> None:
    window = make_window(qtbot)
    window.set_theme("light")
    assert window.theme.id == "light"
    assert Settings.load().appearance.theme == "light"

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.editor.commenting import CommentMode
from forge.editor.lexers import language_by_id
from forge.i18n.translator import install_language
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
    assert window.tabs.tabText(window.tabs.indexOf(tab)) == "notes.txt"
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


def _fake_save_dialog(monkeypatch: pytest.MonkeyPatch, file: Path, use_filter: bool) -> list[str]:
    seen: list[str] = []

    def fake(_parent, _caption, directory, filters, selected):  # type: ignore[no-untyped-def]
        seen.append(directory)
        return str(file), (selected if use_filter else filters.split(";;")[-1])

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake)
    return seen


def test_save_as_keeps_chosen_language_and_adds_extension(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText('{"a": 1}')
    window.set_document_language(language_by_id("json"))
    seen = _fake_save_dialog(monkeypatch, tmp_path / "data", use_filter=True)

    assert window.save_as(tab)
    assert seen[0].endswith("new 1.json")
    assert tab.doc.path == tmp_path / "data.json"
    assert (tmp_path / "data.json").read_text() == '{"a": 1}'
    assert tab.language.id == "json"


def test_save_as_without_extension_keeps_language(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    window.set_document_language(language_by_id("json"))
    _fake_save_dialog(monkeypatch, tmp_path / "data", use_filter=False)  # "All files"

    assert window.save_as(tab)
    assert tab.doc.path == tmp_path / "data"
    assert tab.language.id == "json"


def test_save_as_follows_a_real_extension(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    _fake_save_dialog(monkeypatch, tmp_path / "script.py", use_filter=False)
    assert window.save_as(tab)
    assert tab.language.id == "python"


def test_save_as_asks_before_overwriting_after_adding_extension(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = tmp_path / "data.json"
    existing.write_text("keep")
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("new content")
    window.set_document_language(language_by_id("json"))
    _fake_save_dialog(monkeypatch, tmp_path / "data", use_filter=True)
    monkeypatch.setattr(QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)

    assert not window.save_as(tab)
    assert existing.read_text() == "keep"


def test_dirty_marker_does_not_change_tab_text(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    before = window.tabs.tabText(0)
    tab.setText("x")
    assert window.tabs.tabText(0) == before
    button = window._close_button(tab)
    assert button is not None and button.property("dirty") == "true"


@pytest.mark.parametrize("language", ["en", "nl"])
def test_menu_accelerators_are_unique(qtbot: QtBot, language: str) -> None:
    install_language(language)
    try:
        window = make_window(qtbot)
        bar = window._menu_bar
        menus = [bar, *(a.menu() for a in bar.actions() if a.menu() is not None)]
        for menu in list(menus):
            for action in menu.actions():  # type: ignore[union-attr]
                if action.menu() is not None:
                    menus.append(action.menu())
        for menu in menus:
            keys = [
                m.group(1).lower()
                for a in menu.actions()  # type: ignore[union-attr]
                if (m := re.search(r"&([^&])", a.text()))
            ]
            dupes = {k for k in keys if keys.count(k) > 1}
            assert not dupes, f"{language}: duplicate accelerators {dupes} in {menu}"
    finally:
        install_language("en")


def test_ctrl_q_toggles_comment_in_editor(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.py"
    file.write_text("x = 1\ny = 2\n")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    tab.selectAll()
    window._comment(CommentMode.TOGGLE)
    assert tab.text() == "# x = 1\n# y = 2\n"
    window._comment(CommentMode.TOGGLE)
    assert tab.text() == "x = 1\ny = 2\n"
    tab.undo()
    assert tab.text() == "# x = 1\n# y = 2\n"  # one undo step per toggle


def test_menu_lives_in_the_window(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    assert window.menuWidget() is window.header
    assert not window._menu_bar.isNativeMenuBar()


def test_language_picker_filters_and_chooses(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    picker = window._language_menu.picker
    picker.reset()
    picker.filter.setText("yam")
    visible = [item.text() for item in picker.visible_items()]
    assert visible == ["YAML"]
    picker.choose_current()
    tab = window.current_tab()
    assert tab is not None and tab.language.id == "yaml"


def test_language_picker_shows_ten_rows(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    picker = window._language_menu.picker
    row = picker.list.sizeHintForRow(0)
    assert picker.list.height() < row * 11
    assert picker.list.count() > 10  # the rest scrolls


def test_plus_button_opens_new_tab_next_to_last_tab(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    window.show()
    qtbot.waitExposed(window)
    window._new_tab_button.click()
    assert window.tabs.count() == 2
    qtbot.wait(10)
    bar = window._tab_bar()
    last = bar.tabRect(bar.count() - 1)
    assert window._new_tab_button.x() >= bar.geometry().x() + last.right()


def test_session_restores_tabs_unsaved_text_and_active_tab(qtbot: QtBot, tmp_path: Path) -> None:
    clean = tmp_path / "clean.txt"
    clean.write_text("on disk\n")
    edited = tmp_path / "edited.json"
    edited.write_text("{}\n")

    first = make_window(qtbot)
    first.open_path(clean)
    edited_tab = first.open_path(edited)
    assert edited_tab is not None
    edited_tab.setText('{"unsaved": true}\n')
    untitled = first.new_document()
    untitled.setText("scratch notes")
    first.tabs.setCurrentWidget(edited_tab)
    first.close()  # no questions, the session keeps everything

    second = make_window(qtbot)
    titles = [tab.title for tab in second.all_tabs()]
    assert titles == ["clean.txt", "edited.json", "new 1"]
    restored = {tab.title: tab for tab in second.all_tabs()}
    assert not restored["clean.txt"].is_dirty
    assert restored["edited.json"].text() == '{"unsaved": true}\n'
    assert restored["edited.json"].is_dirty
    assert restored["edited.json"].language.id == "json"
    assert edited.read_text() == "{}\n"  # the file itself is untouched
    assert restored["new 1"].text() == "scratch notes"
    assert second.current_tab() is restored["edited.json"]

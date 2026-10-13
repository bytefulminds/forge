from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.tools.compare.view import CompareView
from forge.tools.find_in_files.panel import FindInFilesPanel
from forge.ui.main_window import MainWindow


def make_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def test_tools_menu_lists_all_tools(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    for command in ("json.format", "yaml.validate", "xml.pretty", "compare.tab"):
        assert command in window.extension_host.actions
    assert "find_in_files.open" in window.extension_host.actions


def test_format_json_command_is_one_undo_step(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText('{"a":[1,2]}')
    window.extension_host.run_command("json.format")
    assert tab.text() == '{\n    "a": [\n        1,\n        2\n    ]\n}'
    assert tab.language.id == "json"
    tab.undo()
    assert tab.text() == '{"a":[1,2]}'


def test_invalid_json_jumps_to_error(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText('{\n  "a": 1,\n  "b":\n}')
    window.extension_host.run_command("json.validate")
    assert tab.notice is not None and tab.notice.kind == "warning"
    assert tab.getCursorPosition()[0] == 3


def test_xml_autoclose_on_typing(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    window.extension_host.start()
    tab = window.current_tab()
    assert tab is not None
    tab.set_language(__import__("forge.editor.lexers", fromlist=["x"]).language_by_id("xml"))
    tab.setText("<item")
    tab.setCursorPosition(0, 5)
    tab.SendScintilla(tab.SCI_ADDTEXT, 1, b">")
    window._on_char_added(tab, ord(">"))
    assert tab.text() == "<item></item>"
    assert tab.getCursorPosition() == (0, 6)


def test_failing_tool_does_not_crash(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    window.extension_host._call("forge.json", "forge.tools.nowhere:missing")
    assert "problem" in window.status.currentMessage()


def test_compare_with_saved_opens_a_tool_tab(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("one\ntwo\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    tab.setText("one\n2\nthree\n")
    window.extension_host.run_command("compare.saved")
    view = window.tabs.currentWidget()
    assert isinstance(view, CompareView)
    assert view.comparison.changed == 1 and view.comparison.added == 1
    assert window.current_tab() is None  # a tool tab is not a document
    left_title = view.left_label.text()
    view.swap()
    assert view.right_label.text() == left_title
    assert view.comparison.removed == 1 and view.comparison.added == 0
    assert view.left.text().startswith("one\n2\nthree")
    window.close_tool_tab(view)
    assert all(
        not isinstance(window.tabs.widget(i), CompareView) for i in range(window.tabs.count())
    )


def test_find_in_files_panel(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "x.txt").write_text("hello world\nbye\n", newline="")
    (tmp_path / "y.md").write_text("say hello\n", newline="")
    window = make_window(qtbot)
    window.extension_host.run_command("find_in_files.open")
    dock = window._panels["find-in-files"]
    panel = dock.widget()
    assert isinstance(panel, FindInFilesPanel)
    panel.folder_edit.setText(str(tmp_path))
    panel.find_edit.setText("hello")
    panel.find_all()
    panel.wait()
    qtbot.waitUntil(lambda: "2 " in panel.status.text(), timeout=3000)
    assert panel.results.topLevelItemCount() == 2

    first_hit = panel.results.topLevelItem(0).child(0)  # type: ignore[union-attr]
    panel._open_hit(first_hit)
    tab = window.current_tab()
    assert tab is not None and tab.selectedText() == "hello"

    panel.replace_edit.setText("hi")
    from PyQt6.QtWidgets import QMessageBox

    from forge.ui import message_box

    monkeypatch.setattr(message_box, "question", lambda *_a, **_k: QMessageBox.StandardButton.Yes)
    panel.replace_all()
    panel.wait()
    qtbot.waitUntil(lambda: "replaced" in panel.status.text(), timeout=3000)
    assert (tmp_path / "y.md").read_text() == "say hi\n"


def test_compare_sides_scroll_together_line_by_line(qtbot: QtBot, tmp_path: Path) -> None:
    from PyQt6.QtWidgets import QApplication

    long = "x" * 400  # would wrap differently on both sides with word wrap on
    old = [f"line {i} {long if i % 7 == 0 else ''}" for i in range(200)]
    new = list(old)
    new[20] = "changed 20"
    del new[60:63]
    new.insert(120, "added")
    file = tmp_path / "a.txt"
    file.write_text("\n".join(old) + "\n", newline="")
    window = make_window(qtbot)
    window.settings.editor.word_wrap = True
    window.resize(900, 500)
    window.show()
    tab = window.open_path(file)
    assert tab is not None
    tab.setText("\n".join(new) + "\n")
    window.extension_host.run_command("compare.saved")
    view = window.tabs.currentWidget()
    assert isinstance(view, CompareView)
    assert view.left.lines() == view.right.lines()

    def settle() -> None:
        for _ in range(5):
            QApplication.processEvents()

    settle()
    view.left.SendScintilla(view.left.SCI_SETFIRSTVISIBLELINE, 90)
    settle()
    assert view.first_visible_rows() == (90, 90)
    view.right.SendScintilla(view.right.SCI_LINESCROLL, 0, -25)
    settle()
    assert view.first_visible_rows() == (65, 65)
    for _ in range(4):
        view.jump(1)
        settle()
        left, right = view.first_visible_rows()
        assert left == right
        assert view.left.getCursorPosition()[0] == view.right.getCursorPosition()[0]
    view.jump(-1)
    settle()
    assert view.first_visible_rows()[0] == view.first_visible_rows()[1]

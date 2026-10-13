from __future__ import annotations

import re
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QPushButton
from pytestqt.qtbot import QtBot

from forge.core.encoding import TextEncoding
from forge.core.eol import Eol
from forge.core.settings import Settings
from forge.editor.commenting import CommentMode
from forge.editor.lexers import language_by_id
from forge.i18n.translator import install_language
from forge.ui import file_dialogs, message_box
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
    file.write_text('{"a": 1}\n', newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    assert window.tabs.count() == 1
    assert tab.text() == '{"a": 1}\n'
    assert tab.language.id == "json"
    assert not tab.is_dirty


def test_opening_same_file_twice_reuses_tab(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("x", newline="")
    window = make_window(qtbot)
    window.new_document().setText("keep me")
    first = window.open_path(file)
    second = window.open_path(file)
    assert first is second
    assert window.tabs.count() == 3  # new 1, new 2 (edited) and a.txt


def test_edit_and_save(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "notes.txt"
    file.write_text("one\r\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    tab.append("two\r\n")
    assert tab.is_dirty
    assert window.tabs.tabText(window._index_of(tab)) == "notes.txt"
    assert window.save(tab)
    assert not tab.is_dirty
    assert file.read_bytes() == b"one\r\ntwo\r\n"


def test_close_dirty_tab_can_be_cancelled(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("unsaved")
    monkeypatch.setattr(
        message_box, "question", lambda *_a, **_k: QMessageBox.StandardButton.Cancel
    )
    assert not window.close_tab(tab)
    assert window.tabs.count() == 1

    monkeypatch.setattr(
        message_box, "question", lambda *_a, **_k: QMessageBox.StandardButton.Discard
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
        return str(file), (selected if use_filter else filters[-1])

    monkeypatch.setattr(file_dialogs, "get_save_file", fake)
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
    existing.write_text("keep", newline="")
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("new content")
    window.set_document_language(language_by_id("json"))
    _fake_save_dialog(monkeypatch, tmp_path / "data", use_filter=True)
    monkeypatch.setattr(message_box, "question", lambda *_a, **_k: QMessageBox.StandardButton.No)

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
    file.write_text("x = 1\ny = 2\n", newline="")
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
    assert picker.visible_labels() == ["YAML"]
    picker.choose_current()
    tab = window.current_tab()
    assert tab is not None and tab.language.id == "yaml"


def test_language_picker_shows_ten_rows(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    picker = window._language_menu.picker
    row = picker.list.sizeHintForRow(0)
    assert picker.list.height() < row * 11
    assert picker.total_count > 10  # the rest scrolls


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
    clean.write_text("on disk\n", newline="")
    edited = tmp_path / "edited.json"
    edited.write_text("{}\n", newline="")

    first = make_window(qtbot)
    first.open_path(clean)
    edited_tab = first.open_path(edited)
    assert edited_tab is not None
    edited_tab.setText('{"unsaved": true}\n')
    untitled = first.new_document()
    untitled.setText("scratch notes")
    first._show(edited_tab)
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


def _bump(path: Path, text: str) -> None:
    import os

    path.write_text(text, newline="")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))


def test_clean_tab_reloads_when_file_changes(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("old\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    _bump(file, "new\n")
    window.watcher.check_all()
    qtbot.waitUntil(lambda: tab.text() == "new\n", timeout=3000)
    assert not tab.is_dirty


def test_dirty_tab_gets_a_notice_instead_of_reload(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("old\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    tab.setText("mine\n")
    _bump(file, "theirs\n")
    window.watcher.check_all()
    qtbot.waitUntil(lambda: tab.notice is not None, timeout=3000)
    assert tab.text() == "mine\n"
    assert not window.notice_bar.isHidden()
    window.notice_bar.buttons[0].click()  # Reload from Disk
    assert tab.text() == "theirs\n"
    assert tab.notice is None


def test_deleted_file_keeps_text_and_marks_dirty(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("keep me\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    file.unlink()
    window.watcher.check_all()
    qtbot.waitUntil(lambda: tab.notice is not None, timeout=3000)
    assert tab.is_dirty
    assert tab.text() == "keep me\n"
    window.notice_bar.buttons[0].click()  # Save
    assert file.read_text() == "keep me\n"


def test_own_save_is_not_an_external_change(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("one\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    tab.setText("two\n")
    assert window.save(tab)
    window.watcher.check_all()
    qtbot.wait(400)
    assert tab.notice is None
    assert tab.text() == "two\n"


def test_convert_eol(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_bytes(b"a\nb\n")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    window.convert_eol(Eol.CRLF)
    assert tab.doc.eol is Eol.CRLF
    assert tab.is_dirty
    assert window.save(tab)
    assert file.read_bytes() == b"a\r\nb\r\n"
    assert window.status.eol.text() == "Windows (CR LF)"


def test_convert_and_reinterpret_encoding(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_bytes("café\n".encode("cp1252"))
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    window.reinterpret_encoding(TextEncoding("cp1252"))
    assert tab.text() == "café\n"
    window.convert_encoding(TextEncoding("utf-8", bom=True))
    assert window.save(tab)
    assert file.read_bytes() == b"\xef\xbb\xbfcaf\xc3\xa9\n"
    assert window.status.encoding.text() == "UTF-8 BOM"


def test_large_file_loads_in_background_without_highlighting(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import forge.ui.main_window as mw

    monkeypatch.setattr(mw, "ASYNC_LOAD_BYTES", 1000)
    monkeypatch.setattr(mw, "LARGE_FILE_BYTES", 1000)
    file = tmp_path / "big.json"
    body = '{"k": 1}\n' * 2000
    file.write_text(body, newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    assert tab.loading and tab.isReadOnly()
    qtbot.waitUntil(lambda: not tab.loading, timeout=5000)
    assert tab.text() == body
    assert not tab.is_dirty
    assert tab.large_file and tab.lexer() is None
    assert tab.language.id == "json"
    assert tab.notice is not None and tab.notice.kind == "info"
    window.notice_bar.buttons[0].click()  # Turn Highlighting On
    assert tab.lexer() is not None


def test_find_bar_incremental_search_and_replace_all(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("alpha beta\nbeta gamma\nBETA\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    window.open_find()
    bar = window.find_bar
    assert bar.isVisibleTo(window)
    bar.find_edit.setText("beta")
    bar.refresh(move=True)
    assert tab.selectedText() == "beta"
    assert bar.count.text() == "1 of 3"
    bar.find_next()
    assert bar.count.text() == "2 of 3"
    bar.match_case.setChecked(True)
    bar.refresh()
    assert "2" in bar.count.text()

    window.open_replace()
    bar.find_edit.setText("beta")
    bar.replace_edit.setText("delta")
    bar.replace_everything()
    assert tab.text() == "alpha delta\ndelta gamma\nBETA\n"
    tab.undo()
    assert tab.text() == "alpha beta\nbeta gamma\nBETA\n"


def test_find_bar_flags_invalid_regex(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("abc")
    window.open_find()
    window.find_bar.regex.setChecked(True)
    window.find_bar.find_edit.setText("(abc")
    window.find_bar.refresh()
    assert window.find_bar.find_edit.property("invalid") == "true"


def test_find_bar_prefills_selection_and_escape_closes(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    window.show()
    tab = window.current_tab()
    assert tab is not None
    tab.setText("hello world")
    tab.setSelection(0, 6, 0, 11)
    window.open_find()
    assert window.find_bar.find_edit.text() == "world"
    qtbot.keyClick(window.find_bar.find_edit, Qt.Key.Key_Escape)
    assert window.find_bar.isHidden()


def test_go_to_line_dialog(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from forge.ui.goto_dialog import GoToLineDialog

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("\n".join(f"line {i}" for i in range(1, 51)))

    def fake_exec(dialog: GoToLineDialog) -> int:
        dialog.spin.setValue(42)
        return GoToLineDialog.DialogCode.Accepted.value

    monkeypatch.setattr(GoToLineDialog, "exec", fake_exec)
    window.go_to_line()
    assert tab.getCursorPosition() == (41, 0)


def test_preferences_preview_ok_and_cancel(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from forge.ui.preferences import PreferencesDialog

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None

    def change_and_cancel(dialog: PreferencesDialog) -> int:
        dialog.tab_width.setValue(2)
        dialog.theme.setCurrentIndex(dialog.theme.findData("light"))
        assert tab.tabWidth() == 2  # live preview
        assert window.theme.id == "light"
        dialog.reject()
        return PreferencesDialog.DialogCode.Rejected.value

    monkeypatch.setattr(PreferencesDialog, "exec", change_and_cancel)
    window.open_preferences()
    assert tab.tabWidth() == 4
    assert window.theme.id == "dark"

    def change_and_accept(dialog: PreferencesDialog) -> int:
        dialog.word_wrap.setChecked(True)
        dialog.indent.setCurrentIndex(dialog.indent.findData(False))
        return PreferencesDialog.DialogCode.Accepted.value

    monkeypatch.setattr(PreferencesDialog, "exec", change_and_accept)
    window.open_preferences()
    assert window.settings.editor.word_wrap
    assert window._view_actions["wrap"].isChecked()  # View menu follows
    assert tab.indentationsUseTabs()
    assert Settings.load().editor.word_wrap  # saved


def test_follow_system_theme(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    import forge.ui.main_window as mw

    monkeypatch.setattr(mw, "system_prefers_dark", lambda _app: False)
    window = make_window(qtbot)
    window.set_theme("system")
    assert window.theme.id == "light"
    assert window._theme_actions["system"].isChecked()


def test_session_off_starts_empty(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("x", newline="")
    settings = Settings()
    settings.general.remember_session = False
    first = MainWindow(settings)
    qtbot.addWidget(first)
    first.open_path(file)
    first.close()
    second = make_window(qtbot)
    assert [t.title for t in second.all_tabs()] == ["new 1"]


def test_language_filter_removes_rows_instead_of_hiding(qtbot: QtBot) -> None:
    # Hidden rows break Qt's accessibility indexes on macOS; filtered rows
    # must be removed from the view's model instead.
    window = make_window(qtbot)
    picker = window._language_menu.picker
    picker.reset()
    picker.filter.setText("ja")
    model = picker.list.model()
    assert model is not None
    assert model.rowCount() == len(picker.visible_labels()) == 2  # Java, JavaScript
    assert not any(picker.list.isRowHidden(r) for r in range(model.rowCount()))


def test_view_modes_for_markdown_csv_and_json(qtbot: QtBot, tmp_path: Path) -> None:
    from forge.ui.previews import CsvPreview, JsonPreview, MarkdownPreview

    md = tmp_path / "a.md"
    md.write_text("# Title\n\nSome *text*.\n", newline="")
    csv_file = tmp_path / "b.csv"
    csv_file.write_text("x,y\n1,2\n3,4\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(md)
    assert tab is not None
    toolbar = window.page_of(tab).toolbar
    assert not toolbar.mode_buttons["split"].isHidden()
    assert "markdown.bold" in toolbar.tool_buttons
    toolbar.mode_buttons["split"].click()
    assert toolbar.mode_buttons["split"].isChecked()
    page = window.page_of(tab)
    assert isinstance(page.preview, MarkdownPreview)
    assert "Title" in page.preview.browser.toPlainText()
    window.set_view_mode(tab, "preview")
    assert tab.isHidden()

    table_tab = window.open_path(csv_file)
    assert table_tab is not None
    window.set_view_mode(table_tab, "split")
    preview = window.page_of(table_tab).preview
    assert isinstance(preview, CsvPreview)
    assert preview.model.rowCount() == 2 and preview.model.columnCount() == 2

    plain = window.new_document()
    plain_bar = window.page_of(plain).toolbar
    assert plain_bar.mode_buttons["text"].isHidden()  # plain text has no preview
    assert not plain_bar.tool_buttons
    plain.setText('{"a": 1}')
    window.set_document_language(language_by_id("json"))
    assert not plain_bar.mode_buttons["text"].isHidden()
    assert {"json.format", "json.tree"} <= set(plain_bar.tool_buttons)
    window.toggle_preview()
    assert isinstance(window.page_of(plain).preview, JsonPreview)


def test_view_mode_is_restored_with_the_session(qtbot: QtBot, tmp_path: Path) -> None:
    md = tmp_path / "a.md"
    md.write_text("# Title\n", newline="")
    first = make_window(qtbot)
    tab = first.open_path(md)
    assert tab is not None
    first.set_view_mode(tab, "split")
    first.close()
    second = make_window(qtbot)
    restored = second.current_tab()
    assert restored is not None
    assert second.page_of(restored).mode == "split"


def test_problem_in_status_bar(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    window.set_document_language(language_by_id("json"))
    tab.setText('{\n  "a": 1,\n}')
    tab.run_check()
    assert tab.diagnostic is not None
    assert not window.status.problem.isHidden()
    tab.setText('{"a": 1}')
    tab.run_check()
    assert window.status.problem.isHidden()


def test_autocomplete_settings_apply(qtbot: QtBot) -> None:
    from PyQt6.Qsci import QsciScintilla

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    assert tab.autoCompletionSource() == QsciScintilla.AutoCompletionSource.AcsDocument
    window.set_document_language(language_by_id("python"))
    assert tab.autoCompletionSource() == QsciScintilla.AutoCompletionSource.AcsAll
    window.settings.editor.autocomplete = False
    tab.apply_settings(window.settings.editor)
    assert tab.autoCompletionSource() == QsciScintilla.AutoCompletionSource.AcsNone


def test_document_toolbar_runs_tools_and_toggles_wrap(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.new_document()
    tab.setText('{"a":1}')
    window.set_document_language(language_by_id("json"))
    toolbar = window.page_of(tab).toolbar
    toolbar.tool_buttons["json.format"].click()
    assert tab.text() == '{\n    "a": 1\n}'
    wrap_before = window.settings.editor.word_wrap
    toolbar.wrap_button.click()
    assert window.settings.editor.word_wrap is not wrap_before
    other = window.new_document()
    assert window.page_of(other).toolbar.wrap_button.isChecked() is not wrap_before
    window._view_actions["toolbar"].setChecked(False)
    assert toolbar.isHidden()


def test_markdown_toolbar_edits(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.new_document()
    window.set_document_language(language_by_id("markdown"))
    tab.setText("word\nsecond")
    tab.setSelection(0, 0, 0, 4)
    bar = window.page_of(tab).toolbar
    bar.tool_buttons["markdown.bold"].click()
    assert tab.text() == "**word**\nsecond"
    assert tab.selectedText() == "word"
    bar.tool_buttons["markdown.bold"].click()
    assert tab.text() == "word\nsecond"
    tab.selectAll()
    bar.tool_buttons["markdown.numbers"].click()
    assert tab.text() == "1. word\n2. second"
    bar.tool_buttons["markdown.numbers"].click()
    assert tab.text() == "word\nsecond"
    tab.setCursorPosition(0, 0)
    bar.tool_buttons["markdown.heading"].click()
    bar.tool_buttons["markdown.heading"].click()
    assert tab.text() == "## word\nsecond"
    assert "edit.toggle_comment" not in bar.tool_buttons  # Markdown has no comments


def test_csv_tools_in_window(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from forge.tools.csv_tool import actions as csv_actions
    from forge.ui.previews import CsvPreview

    file = tmp_path / "data.csv"
    file.write_text("name;created\nzoe;1700000000\nann;1600000000\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    bar = window.page_of(tab).toolbar
    assert {"csv.delimiter", "csv.sort_asc", "csv.epoch_to_iso", "csv.to_json"} <= set(
        bar.tool_buttons
    )
    assert tab.csv_delimiter == ";"
    assert not window.status.delimiter.isHidden()

    tab.setCursorPosition(1, 1)
    bar.tool_buttons["csv.sort_asc"].click()
    assert tab.text() == "name;created\nann;1600000000\nzoe;1700000000\n"

    tab.setCursorPosition(1, 6)
    window.status.update_position(tab)
    assert "created" in window.status.column.text()
    bar.tool_buttons["csv.epoch_to_iso"].click()
    assert tab.text().splitlines()[1] == "ann;2020-09-13T12:26:40Z"
    tab.undo()
    assert tab.text().splitlines()[1] == "ann;1600000000"

    # Choosing a delimiter reads the file differently, also in the table view.
    monkeypatch.setattr(csv_actions, "_pick", lambda *_a, **_k: ",")
    bar.tool_buttons["csv.delimiter"].click()
    assert tab.csv_delimiter == "," and tab.csv_delimiter_choice == ","
    window.set_view_mode(tab, "split")
    preview = window.page_of(tab).preview
    assert isinstance(preview, CsvPreview) and preview.model.columnCount() == 1
    monkeypatch.setattr(csv_actions, "_pick", lambda *_a, **_k: "")
    bar.tool_buttons["csv.delimiter"].click()
    assert tab.csv_delimiter == ";" and tab.csv_delimiter_choice is None

    bar.tool_buttons["csv.to_json"].click()
    json_tab = window.current_tab()
    assert json_tab is not None and json_tab.language.id == "json"
    assert '"name": "ann"' in json_tab.text()


def test_csv_column_problem_is_underlined(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.new_document()
    window.set_document_language(language_by_id("csv"))
    tab.setText("a,b\n1,2\n3,4,5\n")
    tab.run_check()
    assert tab.diagnostic is not None and tab.diagnostic.line == 3


def test_forge_save_dialog_is_framed_and_returns_the_choice(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.ui.file_dialogs import ForgeFileDialog

    def accept(dialog: ForgeFileDialog) -> int:
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert dialog.files.parent() is dialog.body  # embedded, not a separate window
        dialog.files.selectFile(str(tmp_path / "out.md"))
        return int(ForgeFileDialog.DialogCode.Accepted)

    monkeypatch.setattr(ForgeFileDialog, "exec", accept)
    window = make_window(qtbot)
    path, chosen = file_dialogs.get_save_file(
        window,
        "Save As",
        str(tmp_path / "x.md"),
        ["Markdown (*.md)", "All files (*)"],
        "Markdown (*.md)",
    )
    assert Path(path).name == "out.md" and chosen == "Markdown (*.md)"


def test_framed_message_box_answers(qtbot: QtBot) -> None:
    from forge.ui.message_box import Button, FramedMessageBox

    window = make_window(qtbot)
    buttons = Button.Save | Button.Discard | Button.Cancel
    box = FramedMessageBox("question", "Forge", "Save?", buttons, Button.Save, window)
    qtbot.addWidget(box)
    assert box.windowFlags() & Qt.WindowType.FramelessWindowHint
    box.reject()  # Esc or the close button
    assert box.answer == Button.Cancel
    box = FramedMessageBox("question", "Forge", "Save?", buttons, Button.Save, window)
    qtbot.addWidget(box)
    box.findChildren(QPushButton)[0].click()
    assert box.answer in (Button.Save, Button.Discard, Button.Cancel)
    save = next(b for b in box.findChildren(QPushButton) if b.isDefault())
    save.click()
    assert box.answer == Button.Save


def test_restored_untitled_tab_shows_its_language(qtbot: QtBot) -> None:
    first = make_window(qtbot)
    tab = first.current_tab()
    assert tab is not None
    first.set_document_language(language_by_id("csv"))
    tab.setText("a;b\n1;2\n")
    tab.set_csv_delimiter("|")
    first.close()

    second = make_window(qtbot)
    restored = second.current_tab()
    assert restored is not None and restored.language.id == "csv"
    assert second.status.language.text() == "CSV"
    assert not second.status.delimiter.isHidden()
    assert restored.csv_delimiter_choice == "|"
    assert "csv.sort_asc" in second.page_of(restored).toolbar.tool_buttons


def test_csv_header_row_can_be_switched(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.tools.csv_tool import actions as csv_actions
    from forge.ui.previews import CsvPreview

    file = tmp_path / "people.csv"
    file.write_text("name,age\nann,7\nbob,9\n", newline="")
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None and tab.csv_header  # detected
    window.set_view_mode(tab, "split")
    preview = window.page_of(tab).preview
    assert isinstance(preview, CsvPreview)
    model = preview.model
    horizontal = Qt.Orientation.Horizontal
    assert model.rowCount() == 2 and model.headerData(0, horizontal) == "name"
    assert model.headerData(0, Qt.Orientation.Vertical) == "1"  # data rows count from 1

    monkeypatch.setattr(csv_actions, "_choose", lambda *_a, **_k: False)
    window.page_of(tab).toolbar.tool_buttons["csv.header"].click()
    assert tab.csv_header_choice is False and not tab.csv_header
    assert model.rowCount() == 3 and model.headerData(0, horizontal) == "1"
    tab.setCursorPosition(1, 5)
    window.status.update_position(tab)
    assert window.status.column.text() == "Column 2"  # no name without a header

    window.extension_host.run_command("csv.to_json")
    exported = window.current_tab()
    assert exported is not None and exported.text().startswith('[\n    [\n        "name"')

    window.close()
    second = make_window(qtbot)
    restored = next(t for t in second.all_tabs() if t.doc.path == file)
    assert restored.csv_header_choice is False


def test_json_tree_click_selects_the_item_in_the_code(qtbot: QtBot, tmp_path: Path) -> None:
    from forge.ui.previews import JsonPreview

    file = tmp_path / "a.json"
    file.write_text(
        '{\n  "naïve": "é",\n  "list": [10, {"kind": "x"}]\n}\n', encoding="utf-8", newline=""
    )
    window = make_window(qtbot)
    tab = window.open_path(file)
    assert tab is not None
    window.set_view_mode(tab, "split")
    preview = window.page_of(tab).preview
    assert isinstance(preview, JsonPreview)
    tree = preview.tree
    root = tree.topLevelItem(0)
    assert root is not None
    for _ in range(4):  # children are created lazily, one level per expansion
        tree.expandAll()
    items = {tree.path_of(item): item for item in _all_items(root)}
    tree.itemClicked.emit(items[("list", 1, "kind")], 0)
    assert tab.selectedText() == '"kind"'
    assert tab.getCursorPosition()[0] == 2
    tree.itemClicked.emit(items[("list", 0)], 0)
    assert tab.selectedText() == "10"
    tree.itemClicked.emit(items[("naïve",)], 0)
    assert tab.selectedText() == '"naïve"'


def _all_items(item):  # type: ignore[no-untyped-def]
    yield item
    for index in range(item.childCount()):
        yield from _all_items(item.child(index))

from __future__ import annotations

import re

import pytest
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.extensions.api import ForgeAPI
from forge.ui.main_window import MainWindow

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def make_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def titles(menu) -> list[str]:  # type: ignore[no-untyped-def]
    return [a.text() for a in menu.actions() if a.text()]


def test_tools_menu_has_the_developer_tools(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    for command in ("hash.text", "encode.base64", "case.snake", "generate.uuid", "cron.explain"):
        assert command in window.extension_host.actions


def test_right_click_menu_offers_tools_for_the_selection(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("hello")
    menu = tab.build_context_menu()
    submenus = [a.menu().title() for a in menu.actions() if a.menu() is not None]
    assert "&Generate" in submenus and "&Encode / Decode" not in submenus  # no selection
    tab.selectAll()
    menu = tab.build_context_menu()
    submenus = {a.menu().title(): a.menu() for a in menu.actions() if a.menu() is not None}
    assert {"&Hash", "&Encode / Decode", "&Text"} <= set(submenus)
    encode = next(a for a in submenus["&Encode / Decode"].actions() if a.text() == "Base64 &Encode")
    encode.trigger()
    assert tab.text() == "aGVsbG8="
    assert tab.selectedText() == "aGVsbG8="  # the result stays selected
    tab.undo()
    assert tab.text() == "hello"


def test_selection_conversions_and_errors(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    run = window.extension_host.run_command
    tab.setText("parseHttpResponse")
    tab.selectAll()
    run("case.snake")
    assert tab.text() == "parse_http_response"
    tab.setText("not base64 !")
    tab.selectAll()
    run("decode.base64")
    assert tab.text() == "not base64 !"
    assert "Base64" in window.status.currentMessage()


def test_line_tools_use_the_whole_document_without_selection(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("b10\na\nb2\na\n")
    window.extension_host.run_command("lines.unique")
    assert tab.text() == "b10\na\nb2\n"
    window.extension_host.run_command("lines.sort")
    assert tab.text() == "a\nb2\nb10\n"


def test_uuid_and_dates_are_inserted(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from forge.tools.devtools.dialogs import UuidDialog

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    window.extension_host.run_command("generate.uuid")
    assert UUID.match(tab.text())

    def accept(self: UuidDialog) -> int:
        self.count.setValue(3)
        self.uppercase.setChecked(True)
        return int(self.DialogCode.Accepted)

    monkeypatch.setattr(UuidDialog, "exec", accept)
    tab.setText("")
    window.extension_host.run_command("generate.uuids")
    lines = tab.text().split("\n")
    assert len(lines) == 3 and all(UUID.match(line.lower()) for line in lines)
    assert lines[0] == lines[0].upper()

    tab.setText("")
    window.extension_host.run_command("datetime.epoch")
    assert tab.text().isdigit() and len(tab.text()) == 10


def test_hash_and_dialogs(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from forge.tools.devtools.dialogs import CronDialog, DateTimeDialog

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    shown: list[list[tuple[str, str]]] = []
    monkeypatch.setattr(ForgeAPI, "show_values", lambda _s, _t, rows, _n="": shown.append(rows))
    tab.setText("abc")
    window.extension_host.run_command("hash.text")
    assert ("MD5", "900150983cd24fb0d6963f7d28e17f72") in shown[0]

    api = window.extension_host.api("forge.cron")
    cron_dialog = CronDialog(api, "*/5 * * * *")
    qtbot.addWidget(cron_dialog.dialog)
    assert cron_dialog.summary.text() == "Every 5 minutes"
    assert len(cron_dialog.runs.toPlainText().splitlines()) == CronDialog.RUNS
    cron_dialog.input.setText("not cron")
    assert cron_dialog.summary.text().startswith("Not valid")

    dates = DateTimeDialog(api, "1700000000")
    qtbot.addWidget(dates.dialog)
    assert dates.outputs["ISO 8601 (UTC)"].text() == "2023-11-14T22:13:20Z"
    dates.input.setText("2023-11-14T22:13:20.5Z")
    assert dates.outputs["Unix milliseconds"].text() == "1700000000500"


def _submenus(menu) -> dict:  # type: ignore[no-untyped-def]
    return {a.menu().title(): a.menu() for a in menu.actions() if a.menu() is not None}


def test_tools_menu_holds_only_general_tools(qtbot: QtBot) -> None:
    window = make_window(qtbot)
    bar = window.menuWidget().findChild(type(window.menuBar()))  # the Forge menu bar
    tools = next(a.menu() for a in bar.actions() if a.text() == "T&ools")
    titles = [a.text() for a in tools.actions() if a.text()]
    assert "Co&mpare" in titles and "&Hash" in titles and "C&ron" in titles
    for language in ("&JSON", "&YAML", "&XML Tools", "Mar&kdown", "&CSV"):
        assert language not in titles
    # Language commands keep their shortcuts through the window.
    assert window.extension_host.actions["json.format"] in window.actions()
    assert window.extension_host.actions["markdown.bold"].shortcut().toString() == "Ctrl+B"


def test_language_options_sit_on_the_toolbar(qtbot: QtBot) -> None:
    from forge.editor.lexers import language_by_id

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    window.set_document_language(language_by_id("xml"))
    options = window.page_of(tab).toolbar.tool_buttons["options"].menu()
    assert options is not None
    assert [a.text() for a in options.actions()] == ["&Auto-close Tags"]
    window.set_document_language(language_by_id("csv"))
    options = window.page_of(tab).toolbar.tool_buttons["options"].menu()
    assert {a.text() for a in options.actions()} == {"Use &Local Time", "Epoch in &Milliseconds"}
    window.set_document_language(language_by_id("python"))
    assert "options" not in window.page_of(tab).toolbar.tool_buttons


def test_right_click_menu_fits_language_and_selection(qtbot: QtBot) -> None:
    from forge.editor.lexers import language_by_id

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None

    def entries(text: str, language: str) -> dict[str, list[str]]:
        window.set_document_language(language_by_id(language))
        tab.setText(text)
        tab.selectAll()
        return {name: titles(sub) for name, sub in _submenus(tab.build_context_menu()).items()}

    plain = entries("hello world", "python")
    assert "Base64 &Decode" not in plain["&Encode / Decode"]  # not Base64
    assert "&HTML Escape" not in plain["&Encode / Decode"]  # not markup
    assert "C&ron" not in plain and "Decode JW&T" not in plain["&Encode / Decode"]

    assert "Base64 &Decode" in entries("aGVsbG8gd29ybGQ=", "python")["&Encode / Decode"]
    assert "&HTML Escape" in entries("<b>", "html")["&Encode / Decode"]
    assert "C&ron" in entries("*/5 * * * *", "yaml")
    assert "&Epoch to ISO 8601" in entries("at 1700000000", "text")["&Date and Time"]
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln"
    assert "Decode JW&T" in entries(jwt, "text")["&Encode / Decode"]

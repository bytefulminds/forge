"""JSON package: sort keys, conversions, path queries and the tree jump flash."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.tools.json_tool import convert
from forge.ui.main_window import MainWindow

DATA = (
    '{"b": 1.50, "a": {"z": [1, {"name": "x"}], "A": null},'
    ' "items": [{"name": "p", "price": 2.0}, {"name": "q", "tags": ["a"]}]}'
)


def test_sort_keys_keeps_numbers_as_written() -> None:
    result = convert.sorted_json('{"b": 1.50, "a": {"y": 1e3, "X": true}}', "  ")
    assert result == '{\n  "a": {\n    "X": true,\n    "y": 1e3\n  },\n  "b": 1.50\n}'


def test_to_csv_flattens_objects_and_unions_columns() -> None:
    text = '[{"id": 1, "addr": {"city": "Wijchen"}}, {"id": 2, "x": "a,b", "t": [1]}]'
    assert convert.to_csv(text).splitlines() == [
        "id,addr.city,x,t",
        "1,Wijchen,,",
        '2,,"a,b",[1]',
    ]
    assert convert.to_csv("[[1, 2], [3, null]]") == "1,2\n3,\n"
    with pytest.raises(convert.ConvertError):
        convert.to_csv("42")


def test_yaml_round_trip() -> None:
    yaml_text = convert.to_yaml('{"name": "Forge", "tags": ["a", "b"], "n": 1.5}')
    assert yaml_text == "name: Forge\ntags:\n- a\n- b\nn: 1.5\n"
    assert convert.yaml_to_json("a: 1\nwhen: 2020-01-02\n", "  ") == (
        '{\n  "a": 1,\n  "when": "2020-01-02"\n}'
    )
    assert convert.yaml_to_json("a: 1\n---\nb: 2\n", "", "\n").startswith("[")


@pytest.mark.parametrize(
    ("expression", "paths"),
    [
        ("$.items[0].name", [("items", 0, "name")]),
        ("items[*].price", [("items", 0, "price")]),
        ("$..name", [("a", "z", 1, "name"), ("items", 0, "name"), ("items", 1, "name")]),
        ("$['a'].z[-1]", [("a", "z", 1)]),
        ("$.items.*.tags[0]", [("items", 1, "tags", 0)]),
        ("$.missing", []),
        ("$", [()]),
    ],
)
def test_query_paths(expression: str, paths: list[tuple[str | int, ...]]) -> None:
    matches = convert.query(DATA, expression)
    assert [match.path for match in matches] == paths
    for match in matches:
        convert.load_exact(DATA[match.start : match.end])  # each range is one value


def test_query_ranges_cover_the_value() -> None:
    (match,) = convert.query(DATA, "$.a.z[1]")
    assert DATA[match.start : match.end] == '{"name": "x"}'
    assert convert.path_text(("a", "my key", 0)) == '$.a["my key"][0]'
    with pytest.raises(convert.QueryError):
        convert.query(DATA, "$.a[")


def make_json(qtbot: QtBot, text: str) -> tuple[MainWindow, object]:
    from forge.editor.lexers import language_by_id

    window = MainWindow(Settings())
    qtbot.addWidget(window)
    tab = window.current_tab()
    assert tab is not None
    window.set_document_language(language_by_id("json"))
    tab.setText(text)
    return window, tab


def test_conversion_commands_open_new_tabs(qtbot: QtBot) -> None:
    window, tab = make_json(qtbot, '[{"a": 1}, {"a": 2, "b": "x"}]')
    window.extension_host.run_command("json.to_csv")
    csv_tab = window.current_tab()
    assert csv_tab is not tab and csv_tab is not None
    assert csv_tab.text() == "a,b\n1,\n2,x\n"
    assert csv_tab.language.id == "csv"
    window.tabs.setCurrentIndex(0)
    window.extension_host.run_command("json.to_yaml")
    yaml_tab = window.current_tab()
    assert yaml_tab is not None and yaml_tab.language.id == "yaml"
    window.extension_host.run_command("yaml.to_json")
    json_tab = window.current_tab()
    assert json_tab is not None and json_tab.language.id == "json"
    assert convert.load_exact(json_tab.text()) == convert.load_exact(tab.text())  # type: ignore[attr-defined]


def test_sort_keys_command(qtbot: QtBot) -> None:
    window, tab = make_json(qtbot, '{"b": 1, "a": 2}\n')
    window.extension_host.run_command("json.sort_keys")
    assert tab.text() == '{\n    "a": 2,\n    "b": 1\n}\n'  # type: ignore[attr-defined]


def test_path_query_selects_every_match(qtbot: QtBot) -> None:
    from forge.tools.json_tool.query_dialog import QueryDialog

    window, tab = make_json(qtbot, '{\n  "items": [\n    {"id": 7},\n    {"id": 8}\n  ]\n}')
    window.extension_host.run_command("json.query")
    from PyQt6.QtWidgets import QDialog

    query = next(
        d.property("forgeQuery")
        for d in window.findChildren(QDialog)
        if isinstance(d.property("forgeQuery"), QueryDialog)
    )
    query.field.setText("$.items[*].id")
    query.run()
    assert query.list.count() == 2
    editor = tab
    assert int(editor.SendScintilla(editor.SCI_GETSELECTIONS)) == 2  # type: ignore[attr-defined]
    picked = [
        editor.text()[  # type: ignore[attr-defined]
            int(editor.SendScintilla(editor.SCI_GETSELECTIONNSTART, n)) : int(  # type: ignore[attr-defined]
                editor.SendScintilla(editor.SCI_GETSELECTIONNEND, n)  # type: ignore[attr-defined]
            )
        ]
        for n in range(2)
    ]
    assert picked == ["7", "8"]
    assert editor.flashed_lines() == [2, 3]  # type: ignore[attr-defined]
    query.list.setCurrentRow(1)
    qtbot.wait(10)
    assert editor.selectedText() == "8"  # type: ignore[attr-defined]
    query.field.setText("$.items[")
    query.run()
    assert query.list.count() == 0 and "Not a path" in query.result.text()
    query.dialog.close()


def test_tree_click_flashes_the_line(qtbot: QtBot) -> None:
    window, tab = make_json(qtbot, '{\n  "a": 1,\n  "b": {"c": 2}\n}')
    page = window.page_of(tab)  # type: ignore[arg-type]
    page.reveal_json_path(("b", "c"))
    assert tab.selectedText() == '"c"'  # type: ignore[attr-defined]
    assert tab.flashed_lines() == [2]  # type: ignore[attr-defined]
    tab.clear_flash()  # type: ignore[attr-defined]
    assert tab.flashed_lines() == []  # type: ignore[attr-defined]


def test_selected_text_with_several_selections(qtbot: QtBot) -> None:
    """QScintilla's own selectedText overflows its buffer with several selections."""
    _window, tab = make_json(qtbot, "alpha beta gamma delta " * 20)
    tab.SendScintilla(tab.SCI_SETSEL, 0, 5)  # type: ignore[attr-defined]
    for start in range(6, 400, 23):
        tab.SendScintilla(tab.SCI_ADDSELECTION, start + 4, start)  # type: ignore[attr-defined]
    tab.SendScintilla(tab.SCI_SETMAINSELECTION, 0)  # type: ignore[attr-defined]
    assert tab.selectedText() == "alpha"  # type: ignore[attr-defined]
    assert tab.selection_count() > 10  # type: ignore[attr-defined]

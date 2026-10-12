from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from forge.core.settings import EditorSettings
from forge.editor.forge_editor import ForgeEditor
from forge.editor.search import (
    InvalidPattern,
    SearchOptions,
    find,
    find_all,
    go_to_line,
    replace_all,
    replace_current,
)
from forge.themes.theme import DARK

TEXT = "Foo foo food\nbar Foo\ncafé foo\n"


@pytest.fixture
def editor(qtbot: QtBot) -> ForgeEditor:
    widget = ForgeEditor(EditorSettings(), DARK)
    qtbot.addWidget(widget)
    widget.setText(TEXT)
    widget.setCursorPosition(0, 0)
    return widget


def _texts(editor: ForgeEditor, matches: list[tuple[int, int]]) -> list[str]:
    raw = editor.text().encode("utf-8")
    return [raw[s:e].decode("utf-8") for s, e in matches]


def test_find_all_respects_case_and_whole_word(editor: ForgeEditor) -> None:
    assert len(find_all(editor, "foo", SearchOptions())) == 5
    assert len(find_all(editor, "foo", SearchOptions(match_case=True))) == 3
    assert len(find_all(editor, "foo", SearchOptions(whole_word=True))) == 4


def test_find_moves_forward_and_wraps(editor: ForgeEditor) -> None:
    opts = SearchOptions(match_case=True, whole_word=True)
    first = find(editor, "Foo", opts)
    second = find(editor, "Foo", opts)
    third = find(editor, "Foo", opts)
    assert first is not None and second is not None
    assert first != second
    assert third == first  # wrapped around


def test_find_backwards(editor: ForgeEditor) -> None:
    opts = SearchOptions(match_case=True)
    editor.setCursorPosition(2, 0)
    match = find(editor, "Foo", opts, forward=False)
    assert match is not None
    assert editor.getCursorPosition()[0] == 1


def test_positions_are_utf8_safe(editor: ForgeEditor) -> None:
    matches = find_all(editor, "café", SearchOptions())
    assert _texts(editor, matches) == ["café"]


def test_regex_and_groups(editor: ForgeEditor) -> None:
    opts = SearchOptions(regex=True, match_case=True)
    assert _texts(editor, find_all(editor, r"[Ff]oo\b", opts)) == ["Foo", "foo", "Foo", "foo"]
    count = replace_all(editor, r"(\w+) (Foo)", r"\2 \1", opts)
    assert count == 1
    assert "Foo bar" in editor.text()


def test_invalid_regex_raises(editor: ForgeEditor) -> None:
    with pytest.raises(InvalidPattern):
        find_all(editor, "(unclosed", SearchOptions(regex=True))


def test_replace_all_is_one_undo_step(editor: ForgeEditor) -> None:
    assert replace_all(editor, "foo", "x", SearchOptions()) == 5
    assert "foo" not in editor.text().lower()
    editor.undo()
    assert editor.text() == TEXT


def test_replace_all_handles_growing_replacement(editor: ForgeEditor) -> None:
    assert replace_all(editor, "o", "oo", SearchOptions()) == 10
    assert editor.text().count("o") == 20


def test_replace_current_then_next(editor: ForgeEditor) -> None:
    opts = SearchOptions(match_case=True, whole_word=True)
    find(editor, "foo", opts)
    replace_current(editor, "foo", "bar", opts)
    assert editor.text().startswith("Foo bar food")
    assert editor.selectedText() == "foo"  # next match selected


def test_go_to_line(editor: ForgeEditor) -> None:
    go_to_line(editor, 3)
    assert editor.getCursorPosition() == (2, 0)
    go_to_line(editor, 999)
    assert editor.getCursorPosition()[0] == editor.lines() - 1

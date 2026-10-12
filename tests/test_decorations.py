from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from forge.core.settings import EditorSettings
from forge.editor import decorations
from forge.editor.decorations import bracket_levels, indent_ranges
from forge.editor.diagnostics import Diagnostic, check
from forge.editor.forge_editor import ForgeEditor
from forge.editor.lexers import language_by_id
from forge.themes.theme import DARK


def test_bracket_levels_and_unmatched() -> None:
    data = b"{ [ ( ) ] } ]"
    assert bracket_levels(data) == [(0, 0), (2, 1), (4, 2), (6, 2), (8, 1), (10, 0), (12, -1)]
    assert bracket_levels(b"( [ )") == [(0, -1), (2, -1), (4, -1)]


def test_indent_ranges_spaces_and_tabs() -> None:
    data = b"a\n        b\n\tc\n\n"
    ranges = indent_ranges(data, 4)
    assert ranges == [(2, 4, 0), (6, 4, 1), (12, 1, 0)]


def _indicator_at(editor: ForgeEditor, indicator: int, position: int) -> bool:
    value = editor.SendScintilla(editor.SCI_INDICATORVALUEAT, indicator, position)
    return bool(value)


def test_brackets_in_strings_are_ignored(qtbot: QtBot) -> None:
    editor = ForgeEditor(EditorSettings(), DARK)
    qtbot.addWidget(editor)
    editor.set_language(language_by_id("json"))
    editor.setText('{"a": "{not a bracket"}')
    editor.resize(600, 300)
    editor.refresh_decorations()
    assert _indicator_at(editor, decorations.BRACKET_INDICATORS[0], 0)
    assert not _indicator_at(editor, decorations.BRACKET_UNMATCHED, 7)
    assert not any(_indicator_at(editor, i, 7) for i in decorations.BRACKET_INDICATORS)


@pytest.mark.parametrize(
    ("language", "path", "text", "line"),
    [
        ("json", None, '{\n  "a": 1\n  "b": 2\n}', 3),
        ("yaml", None, "a: [1, 2\nb: 3\n", 2),
        ("xml", None, "<a>\n<b>\n</a>", 3),
        ("python", None, "def f(:\n    pass\n", 1),
        ("properties", "x.toml", 'a = 1\nb = "unclosed\n', 2),
    ],
)
def test_checkers_find_the_error_line(
    language: str, path: str | None, text: str, line: int
) -> None:
    from pathlib import Path

    found = check(language, Path(path) if path else None, text)
    assert isinstance(found, Diagnostic)
    assert found.line == line


def test_valid_documents_have_no_diagnostic() -> None:
    assert check("json", None, '{"a": [1, 2]}') is None
    assert check("python", None, "x = 1\n") is None
    assert check("text", None, "{") is None  # no checker for plain text


def test_squiggle_marks_the_error_token(qtbot: QtBot) -> None:
    editor = ForgeEditor(EditorSettings(), DARK)
    qtbot.addWidget(editor)
    editor.setText('{\n  "a": 1\n  "b": 2\n}')
    editor.set_diagnostic(Diagnostic(3, 3, "Expecting ',' delimiter"))
    start = editor.SendScintilla(editor.SCI_POSITIONFROMLINE, 2) + 2
    assert _indicator_at(editor, decorations.DIAGNOSTIC, start)
    editor.set_diagnostic(None)
    assert not _indicator_at(editor, decorations.DIAGNOSTIC, start)

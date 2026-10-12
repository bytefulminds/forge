from __future__ import annotations

from pytestqt.qtbot import QtBot

from forge.core.csvtext import detect_delimiter, read_rows, split_line
from forge.core.settings import EditorSettings
from forge.editor.csv_lexer import DELIMITER_STYLE
from forge.editor.forge_editor import ForgeEditor
from forge.editor.lexers import language_by_id, language_for_path
from forge.themes.theme import DARK


def test_detect_delimiter() -> None:
    assert detect_delimiter("a,b,c\n1,2,3\n") == ","
    assert detect_delimiter("a;b;c\n1;2,5;3\n") == ";"
    assert detect_delimiter("a\tb\n1\t2\n") == "\t"


def test_split_and_read_with_quotes() -> None:
    assert split_line('1,"Doe, Jane",x', ",") == ["1", '"Doe, Jane"', "x"]
    assert read_rows('a,b\n1,"x, y"\n', ",") == [["a", "b"], ["1", "x, y"]]


def test_csv_files_use_the_csv_language() -> None:
    assert language_for_path(__import__("pathlib").Path("data.csv")).id == "csv"


def test_each_column_gets_its_own_style(qtbot: QtBot) -> None:
    editor = ForgeEditor(EditorSettings(), DARK)
    qtbot.addWidget(editor)
    editor.set_language(language_by_id("csv"))
    editor.setText('a,b,c\n1,"x, y",3\n')
    editor.SendScintilla(editor.SCI_COLOURISE, 0, -1)

    def style(position: int) -> int:
        return int(editor.SendScintilla(editor.SCI_GETSTYLEAT, position))

    assert [style(0), style(2), style(4)] == [0, 1, 2]
    assert style(1) == DELIMITER_STYLE
    second_line = 6
    assert style(second_line + 4) == 1  # the comma inside quotes is not a delimiter

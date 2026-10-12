from __future__ import annotations

from pathlib import Path

import pytest

from forge.editor.lexers import PLAIN_TEXT, all_languages, language_by_id, language_for_path
from forge.ui.main_window import path_for_save

JSON = language_by_id("json")


@pytest.mark.parametrize(
    ("name", "language_id"),
    [
        ("a.json", "json"),
        ("A.YML", "yaml"),
        ("Makefile", "makefile"),
        (".gitlab-ci.yml", "yaml"),
        (".env", "properties"),
        ("notes", "text"),
        ("notes.txt", "text"),
    ],
)
def test_language_for_path(name: str, language_id: str) -> None:
    assert language_for_path(Path(name)).id == language_id


def test_every_language_with_default_extension_detects_itself() -> None:
    for language in all_languages():
        if language.default_extension:
            detected = language_for_path(Path("x" + language.default_extension))
            assert detected is language, language.id


@pytest.mark.parametrize(
    ("chosen", "filter_selected", "expected"),
    [
        ("/tmp/data", True, "/tmp/data.json"),
        ("/tmp/data", False, "/tmp/data"),
        ("/tmp/data.json", True, "/tmp/data.json"),  # never twice (macOS panel)
        ("/tmp/data.txt", True, "/tmp/data.txt"),  # user picked an extension
        ("/tmp/.env", True, "/tmp/.env"),  # dotfile
        ("/tmp/Makefile", True, "/tmp/Makefile"),  # known file name
    ],
)
def test_path_for_save(chosen: str, filter_selected: bool, expected: str) -> None:
    assert path_for_save(Path(chosen), JSON, filter_selected) == Path(expected)


def test_plain_text_gets_txt() -> None:
    assert path_for_save(Path("/tmp/notes"), PLAIN_TEXT, True) == Path("/tmp/notes.txt")

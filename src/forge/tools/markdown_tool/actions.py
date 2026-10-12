"""Markdown commands acting on the active editor."""

from __future__ import annotations

from collections.abc import Callable

from forge.extensions.api import EditorHandle, ForgeAPI
from forge.i18n.translator import tr
from forge.tools.markdown_tool import edits


def _editor(api: ForgeAPI) -> EditorHandle | None:
    editor = api.active_editor()
    # The shortcuts (Ctrl+B, Ctrl+I) are global: only act on Markdown.
    if editor is None or editor.language_id != "markdown" or editor.widget.isReadOnly():
        return None
    return editor


def _wrap(api: ForgeAPI, marker: str) -> None:
    editor = _editor(api)
    if editor is None:
        return
    text = editor.selected_text()
    size = len(marker)
    before, after = editor.text_around_selection(size + 1)
    if text and edits.wrapped_outside(before, after, marker):
        editor.extend_selection(size, size)
        editor.replace_selection_and_select(text, 0, len(text))
        return
    editor.replace_selection_and_select(*edits.toggle_wrap(text, marker))


def _lines(api: ForgeAPI, change: Callable[[list[str]], list[str]]) -> None:
    editor = _editor(api)
    if editor is None:
        return
    first, last = editor.selected_line_range()
    editor.replace_lines(first, last, change(editor.line_texts(first, last)))


def bold(api: ForgeAPI) -> None:
    _wrap(api, "**")


def italic(api: ForgeAPI) -> None:
    _wrap(api, "*")


def inline_code(api: ForgeAPI) -> None:
    _wrap(api, "`")


def link(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is not None:
        editor.replace_selection_and_select(*edits.link(editor.selected_text()))


def heading(api: ForgeAPI) -> None:
    _lines(api, edits.cycle_heading)


def quote(api: ForgeAPI) -> None:
    _lines(api, lambda lines: edits.toggle_prefix(lines, "> "))


def bullets(api: ForgeAPI) -> None:
    _lines(api, edits.toggle_bullets)


def numbers(api: ForgeAPI) -> None:
    _lines(api, edits.toggle_numbers)


def tasks(api: ForgeAPI) -> None:
    _lines(api, edits.toggle_tasks)


def code_block(api: ForgeAPI) -> None:
    _lines(api, edits.toggle_code_block)


def rule(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is not None:
        eol = editor.eol
        text = f"{eol}{eol}---{eol}{eol}"
        editor.replace_selection_and_select(text, len(text), 0)


def table(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is not None:
        labels = [tr("Column {number}", number=n) for n in (1, 2, 3)]
        editor.replace_selection_and_select(edits.table(labels, editor.eol), 2, len(labels[0]))

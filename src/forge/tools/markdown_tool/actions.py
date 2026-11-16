"""Markdown commands acting on the active editor."""

from __future__ import annotations

import os
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


def strikethrough(api: ForgeAPI) -> None:
    _wrap(api, "~~")


def image(api: ForgeAPI) -> None:
    """Insert images picked from disk, relative to the document's folder."""
    editor = _editor(api)
    if editor is None:
        return
    files = api.choose_files(tr("Insert Image"))
    if not files:
        return
    alt = editor.selected_text()
    base = editor.path.parent if editor.path is not None else None
    parts = []
    for file in files:
        target = str(file)
        if base is not None:
            try:
                target = os.path.relpath(file, base)
            except ValueError:  # another drive on Windows
                target = str(file)
        target = target.replace(os.sep, "/").replace(" ", "%20")
        parts.append(f"![{alt or file.stem}]({target})")
    editor.insert(editor.eol.join(parts))


def footnote(api: ForgeAPI) -> None:
    """A numbered footnote: the reference at the caret, its text at the end."""
    editor = _editor(api)
    if editor is None:
        return
    widget = editor.widget
    text = editor.text()
    number = edits.next_footnote(text)
    widget.beginUndoAction()
    try:
        widget.replaceSelectedText(f"[^{number}]")
        widget.append(edits.footnote_definition(str(widget.text()), number, editor.eol))
    finally:
        widget.endUndoAction()
    last = widget.lines() - 1
    widget.setCursorPosition(last, len(str(widget.text(last))))
    widget.ensureCursorVisible()


def toc(api: ForgeAPI) -> None:
    """Insert a table of contents, or bring an existing one up to date."""
    editor = _editor(api)
    if editor is None:
        return
    text = editor.text()
    contents = edits.table_of_contents(text, editor.eol)
    updated = edits.replace_toc(text, contents)
    if updated is not None:
        if updated != text:
            editor.set_text(updated)
        api.status(tr("Table of contents updated."))
        return
    editor.insert(contents + editor.eol)


def format_table(api: ForgeAPI) -> None:
    """Line up the columns of the table at the caret."""
    editor = _editor(api)
    if editor is None:
        return
    first, last = editor.selected_line_range()
    if not edits.is_table_line(editor.line_texts(first, first)[0]):
        api.status(tr("Put the cursor in a table first."))
        return
    while first > 0 and edits.is_table_line(editor.line_texts(first - 1, first - 1)[0]):
        first -= 1
    end = editor.line_count - 1
    while last < end and edits.is_table_line(editor.line_texts(last + 1, last + 1)[0]):
        last += 1
    editor.replace_lines(first, last, edits.format_table(editor.line_texts(first, last)))


def diagram(api: ForgeAPI) -> None:
    """Draw a Mermaid flowchart; edits the flowchart block at the caret."""
    editor = _editor(api)
    if editor is None:
        return
    from forge.tools.markdown_tool.diagram import open_diagram_editor

    open_diagram_editor(api, editor)

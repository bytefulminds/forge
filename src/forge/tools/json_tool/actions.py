"""JSON commands. Work on the selection if there is one, else the whole document."""

from __future__ import annotations

from forge.extensions.api import EditorHandle, ForgeAPI, tr
from forge.tools.json_tool.formatter import JsonError, reformat, validate


def _source(api: ForgeAPI) -> tuple[EditorHandle, str, bool] | None:
    editor = api.active_editor()
    if editor is None:
        return None
    if editor.has_selection():
        return editor, editor.selected_text(), True
    return editor, editor.text(), False


def _report(api: ForgeAPI, editor: EditorHandle, error: JsonError, in_selection: bool) -> None:
    line = error.line + (editor.selection_start_line() - 1 if in_selection else 0)
    api.show_error_at(
        editor,
        tr(
            "Invalid JSON at line {line}, column {column}: {error}",
            line=line,
            column=error.column,
            error=error.message,
        ),
        line,
        error.column,
    )


def _rewrite(api: ForgeAPI, indent: str | None) -> None:
    source = _source(api)
    if source is None:
        return
    editor, text, in_selection = source
    eol = "\r\n" if "\r\n" in text else "\n"
    try:
        result = reformat(text, indent, eol)
    except JsonError as error:
        _report(api, editor, error, in_selection)
        return
    if text.endswith(("\n", "\r")) and not in_selection:
        result += eol
    if in_selection:
        editor.replace_selection(result)
    else:
        editor.set_text(result)
        if editor.language_id == "text":
            editor.set_language("json")
    api.status(tr("JSON formatted.") if indent is not None else tr("JSON minified."))


def format_json(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is not None:
        _rewrite(api, editor.indent_unit())


def minify_json(api: ForgeAPI) -> None:
    _rewrite(api, None)


def validate_json(api: ForgeAPI) -> None:
    source = _source(api)
    if source is None:
        return
    editor, text, in_selection = source
    try:
        validate(text)
    except JsonError as error:
        _report(api, editor, error, in_selection)
        return
    api.notify(tr("Valid JSON."), "info")


# Tree view --------------------------------------------------------------------


def show_tree(api: ForgeAPI) -> None:
    """Show the JSON tree next to the text (the document's split view)."""
    editor = api.active_editor()
    if editor is None:
        return
    if editor.language_id != "json":
        editor.set_language("json")
    api.set_document_view(editor, "split")

"""CSV commands acting on the active editor."""

from __future__ import annotations

from PyQt6.QtGui import QActionGroup, QCursor
from PyQt6.QtWidgets import QMenu

from forge.core import timestamps
from forge.core.csvtext import Record, column_at, join_records, split_records
from forge.extensions.api import EditorHandle, ForgeAPI
from forge.i18n.translator import tr
from forge.tools.csv_tool import ops


def delimiter_label(delimiter: str) -> str:
    return {
        ",": tr("Comma (,)"),
        ";": tr("Semicolon (;)"),
        "\t": tr("Tab"),
        "|": tr("Pipe (|)"),
    }.get(delimiter, delimiter)


DELIMITERS = (",", ";", "\t", "|")


def _editor(api: ForgeAPI, need_csv: bool = True) -> EditorHandle | None:
    editor = api.active_editor()
    if editor is None:
        return None
    if need_csv and editor.language_id != "csv":
        api.status(tr("This command works on CSV documents."))
        return None
    if editor.widget.isReadOnly():
        return None
    return editor


def _records(editor: EditorHandle) -> list[Record]:
    return split_records(editor.text(), editor.csv_delimiter)


def _write(editor: EditorHandle, records: list[Record], delimiter: str | None = None) -> None:
    text = join_records(records, delimiter or editor.csv_delimiter)
    if text != editor.text():
        editor.set_text(text)


def _pick(api: ForgeAPI, current: str | None, include_auto: bool) -> str | None:
    """Popup menu at the mouse; returns the delimiter, "" for automatic, None if cancelled."""
    menu = QMenu(api.window)
    group = QActionGroup(menu)
    choices: dict[object, str] = {}
    if include_auto:
        auto = menu.addAction(tr("Detect Automatically"))
        assert auto is not None
        auto.setCheckable(True)
        auto.setChecked(current is None)
        group.addAction(auto)
        choices[auto] = ""
        menu.addSeparator()
    for delimiter in DELIMITERS:
        action = menu.addAction(delimiter_label(delimiter))
        assert action is not None
        action.setCheckable(True)
        action.setChecked(delimiter == current)
        group.addAction(action)
        choices[action] = delimiter
    chosen = menu.exec(QCursor.pos())
    return choices.get(chosen) if chosen is not None else None


def _choose(api: ForgeAPI, choices: list[tuple[str, object]], current: object) -> object | None:
    """Popup menu at the mouse with checkable ``(label, value)`` choices;
    returns the chosen value, or ``None`` when cancelled."""
    menu = QMenu(api.window)
    group = QActionGroup(menu)
    values: dict[object, object] = {}
    for label, value in choices:
        if label == "-":
            menu.addSeparator()
            continue
        action = menu.addAction(label)
        assert action is not None
        action.setCheckable(True)
        action.setChecked(value == current)
        group.addAction(action)
        values[action] = value
    chosen = menu.exec(QCursor.pos())
    return values.get(chosen) if chosen is not None else None


_AUTO = "auto"


def header_choices() -> list[tuple[str, object]]:
    return [
        (tr("Detect Automatically"), _AUTO),
        ("-", None),
        (tr("First Row Is the Header"), True),
        (tr("No Header Row"), False),
    ]


def choose_header(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is None:
        return
    current = _AUTO if editor.csv_header_choice is None else editor.csv_header_choice
    chosen = _choose(api, header_choices(), current)
    if chosen is None:
        return
    editor.set_csv_header(None if chosen == _AUTO else bool(chosen))
    api.status(tr("First row is the header.") if editor.csv_header else tr("No header row."))


def choose_delimiter(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is None:
        return
    chosen = _pick(api, editor.csv_delimiter_choice, include_auto=True)
    if chosen is None:
        return
    editor.set_csv_delimiter(chosen or None)
    api.status(tr("Delimiter: {name}", name=delimiter_label(editor.csv_delimiter)))


def convert_delimiter(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is None:
        return
    current = editor.csv_delimiter
    chosen = _pick(api, current, include_auto=False)
    if not chosen or chosen == current:
        return
    records = ops.change_delimiter(_records(editor), chosen)
    _write(editor, records, chosen)
    editor.set_csv_delimiter(chosen)
    api.status(tr("Delimiter: {name}", name=delimiter_label(chosen)))


def align_columns(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is not None:
        _write(editor, ops.align(_records(editor)))


def shrink_columns(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is not None:
        _write(editor, ops.shrink(_records(editor)))


def _column(editor: EditorHandle) -> int:
    return column_at(editor.text_before_caret(), editor.csv_delimiter)


def _sort(api: ForgeAPI, descending: bool) -> None:
    editor = _editor(api)
    if editor is None:
        return
    records = _records(editor)
    header = editor.csv_header
    column = _column(editor)
    _write(editor, ops.sort_rows(records, column, descending, header))
    api.status(tr("Sorted by column {number}.", number=column + 1))


def sort_ascending(api: ForgeAPI) -> None:
    _sort(api, descending=False)


def sort_descending(api: ForgeAPI) -> None:
    _sort(api, descending=True)


def remove_duplicates(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is None:
        return
    records = _records(editor)
    kept, removed = ops.remove_duplicates(records, editor.csv_header)
    if removed:
        _write(editor, kept)
    api.status(tr("{count} duplicate rows removed.", count=removed))


def _convert_times(api: ForgeAPI, to_iso: bool) -> None:
    editor = api.active_editor()
    if editor is None or editor.widget.isReadOnly():
        return
    local = bool(api.setting("local_time", False))
    milliseconds = bool(api.setting("epoch_ms", False))
    if editor.has_selection():
        selected = editor.selected_text()
        if to_iso:
            text, count = timestamps.convert_in_text(selected, True, local)
        else:
            text, count = timestamps.convert_in_text(selected, False, milliseconds=milliseconds)
        if count:
            editor.replace_selection_and_select(text, 0, len(text))
        api.status(tr("{count} timestamps converted.", count=count))
        return
    if editor.language_id != "csv":
        api.status(tr("Select the timestamps to convert."))
        return
    records = _records(editor)
    header = editor.csv_header

    def convert(value: str) -> str | None:
        if to_iso:
            return timestamps.epoch_to_iso(value, local)
        return timestamps.iso_to_epoch(value, milliseconds)

    converted, count = ops.convert_column(
        records, _column(editor), convert, header, editor.csv_delimiter
    )
    if count:
        _write(editor, converted)
    api.status(tr("{count} timestamps converted.", count=count))


def epoch_to_iso(api: ForgeAPI) -> None:
    _convert_times(api, to_iso=True)


def iso_to_epoch(api: ForgeAPI) -> None:
    _convert_times(api, to_iso=False)


def setting_changed(api: ForgeAPI) -> None:
    """Checkable settings are stored by Forge; nothing else to do."""


def to_json(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is None:
        return
    records = _records(editor)
    header = editor.csv_header
    api.new_document(ops.to_json(records, header, editor.indent_unit()), "json")


def to_markdown(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is None:
        return
    records = _records(editor)
    header = editor.csv_header
    api.new_document(ops.to_markdown(records, header), "markdown")

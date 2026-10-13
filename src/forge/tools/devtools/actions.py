"""Developer tool commands acting on the active editor."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from forge.core import timestamps
from forge.extensions.api import EditorHandle, ForgeAPI
from forge.i18n.translator import tr
from forge.tools.devtools import datetimes, transforms, uuids

MAX_HASHED_FILES = 20


def _editor(api: ForgeAPI) -> EditorHandle | None:
    editor = api.active_editor()
    if editor is None or editor.widget.isReadOnly():
        return None
    return editor


def _convert_selection(api: ForgeAPI, convert: Callable[[str], str]) -> None:
    """Replace the selection by ``convert(selection)`` (one undo step)."""
    editor = _editor(api)
    if editor is None:
        return
    if not editor.has_selection():
        api.status(tr("Select the text to convert first."))
        return
    try:
        result = convert(editor.selected_text())
    except ValueError as exc:
        api.status(tr("Could not convert the selection: {reason}", reason=str(exc)))
        return
    editor.replace_selection_and_select(result, 0, len(result))


def _convert_lines(api: ForgeAPI, convert: Callable[[list[str]], list[str]]) -> None:
    """Apply ``convert`` to the selected lines, or to the whole document."""
    editor = _editor(api)
    if editor is None:
        return
    if editor.has_selection():
        first, last = editor.selected_line_range()
    else:
        first, last = 0, max(0, editor.line_count - 1)
    lines = editor.line_texts(first, last)
    # A final empty line (the document ends with a line break) stays last.
    trailing = [] if not lines or lines[-1] else [lines.pop()]
    editor.replace_lines(first, last, convert(lines) + trailing)


# Hashes --------------------------------------------------------------------------------


def hash_selection(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None:
        return
    if editor.has_selection():
        text, note = editor.selected_text(), tr("Hashes of the selected text (UTF-8).")
    else:
        text, note = editor.text(), tr("Hashes of the whole document (UTF-8).")
    rows = [
        (transforms.HASH_LABELS[name], transforms.hash_text(text, name))
        for name in transforms.HASHES
    ]
    api.show_values(tr("Hash"), rows, note)


def hash_files(api: ForgeAPI) -> None:
    files = api.choose_files(tr("Choose Files to Hash"))[:MAX_HASHED_FILES]
    if not files:
        return

    def work() -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for path in files:
            for name, digest in transforms.hash_file(path).items():
                rows.append((f"{path.name}  {transforms.HASH_LABELS[name]}", digest))
        return rows

    def done(rows: list[tuple[str, str]]) -> None:
        api.show_values(tr("Hash"), rows, ", ".join(str(Path(f)) for f in files))

    api.status(tr("Hashing {count} files...", count=len(files)))
    api.run_in_background(work, done, lambda exc: api.status(str(exc)))


# Encodings ------------------------------------------------------------------------------


def base64_encode(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.base64_encode)


def base64_decode(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.base64_decode)


def url_encode(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.url_encode)


def url_decode(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.url_decode)


def html_escape(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.html_escape)


def html_unescape(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.html_unescape)


def json_escape(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.json_escape)


def json_unescape(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.json_unescape)


def decode_jwt(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None or not editor.has_selection():
        api.status(tr("Select the token to decode first."))
        return
    try:
        decoded = transforms.decode_jwt(editor.selected_text())
    except ValueError as exc:
        api.status(tr("Could not convert the selection: {reason}", reason=str(exc)))
        return
    payload = decoded.get("payload")
    if isinstance(payload, dict):
        times = {
            key: timestamps.epoch_to_iso(str(payload[key]))
            for key in ("iat", "nbf", "exp")
            if isinstance(payload.get(key), int)
        }
        if times:
            decoded["times (UTC)"] = times
    api.new_document(json.dumps(decoded, indent=4, ensure_ascii=False) + "\n", "json")
    api.status(tr("The signature is not verified."))


# Letter case and lines ---------------------------------------------------------------------


def upper_case(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.upper_case)


def lower_case(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.lower_case)


def title_case(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.title_case)


def camel_case(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.camel_case)


def pascal_case(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.pascal_case)


def snake_case(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.snake_case)


def kebab_case(api: ForgeAPI) -> None:
    _convert_selection(api, transforms.kebab_case)


def sort_lines_ascending(api: ForgeAPI) -> None:
    _convert_lines(api, transforms.sort_lines)


def sort_lines_descending(api: ForgeAPI) -> None:
    _convert_lines(api, lambda lines: transforms.sort_lines(lines, descending=True))


def unique_lines(api: ForgeAPI) -> None:
    _convert_lines(api, transforms.unique_lines)


def reverse_lines(api: ForgeAPI) -> None:
    _convert_lines(api, transforms.reverse_lines)


def trim_trailing(api: ForgeAPI) -> None:
    _convert_lines(api, transforms.trim_trailing)


# Generate ------------------------------------------------------------------------------------


def insert_uuid(api: ForgeAPI) -> None:
    editor = _editor(api)
    if editor is not None:
        editor.insert(uuids.generate(uuids.UuidOptions()))


def insert_uuids(api: ForgeAPI) -> None:
    from forge.tools.devtools.dialogs import UuidDialog

    editor = _editor(api)
    if editor is None:
        return
    dialog = UuidDialog(api)
    if dialog.exec() == dialog.DialogCode.Accepted:
        editor.insert(uuids.generate(dialog.options()).replace("\n", editor.eol))


# Date and time ---------------------------------------------------------------------------------


def _insert(api: ForgeAPI, text: str) -> None:
    editor = _editor(api)
    if editor is not None:
        editor.insert(text)


def insert_now(api: ForgeAPI) -> None:
    _insert(api, datetimes.now_iso_local())


def insert_now_utc(api: ForgeAPI) -> None:
    _insert(api, datetimes.now_iso_utc())


def insert_today(api: ForgeAPI) -> None:
    _insert(api, datetimes.today())


def insert_epoch(api: ForgeAPI) -> None:
    _insert(api, datetimes.now_epoch())


def _convert_times(api: ForgeAPI, to_iso: bool) -> None:
    editor = _editor(api)
    if editor is None:
        return
    if not editor.has_selection():
        api.status(tr("Select the timestamps to convert."))
        return
    local = bool(api.setting("local_time", False))
    text, count = timestamps.convert_in_text(editor.selected_text(), to_iso, local)
    if count:
        editor.replace_selection_and_select(text, 0, len(text))
    api.status(tr("{count} timestamps converted.", count=count))


def epoch_to_iso(api: ForgeAPI) -> None:
    _convert_times(api, to_iso=True)


def iso_to_epoch(api: ForgeAPI) -> None:
    _convert_times(api, to_iso=False)


def _selection(api: ForgeAPI) -> str:
    editor = api.active_editor()
    if editor is None or not editor.has_selection():
        return ""
    return editor.selected_text().strip().splitlines()[0] if editor.selected_text().strip() else ""


def converter(api: ForgeAPI) -> None:
    from forge.tools.devtools.dialogs import DateTimeDialog

    DateTimeDialog(api, _selection(api) or str(int(datetime.now(UTC).timestamp()))).exec()


def explain_cron(api: ForgeAPI) -> None:
    from forge.tools.devtools.dialogs import CronDialog

    CronDialog(api, _selection(api) or "0 9 * * MON-FRI").exec()


def setting_changed(api: ForgeAPI) -> None:
    """Checkable settings are stored by Forge; nothing else to do."""

"""Close XML and HTML tags automatically when ">" is typed (XML Tools "Tag auto-close")."""

from __future__ import annotations

import re

from PyQt6.Qsci import QsciScintilla

from forge.extensions.api import EditorHandle, ForgeAPI

_OPEN_TAG = re.compile(r"<([A-Za-z_][\w:.-]*)(?:\s[^<>]*)?>$")
_HTML_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}  # fmt: skip
_LANGUAGES = {"xml", "html"}


def closing_tag(before_caret: str, language_id: str) -> str | None:
    """The closing tag to insert after typing ``>``, or None."""
    if language_id not in _LANGUAGES or before_caret.endswith("/>"):
        return None
    match = _OPEN_TAG.search(before_caret)
    if match is None:
        return None
    name = match.group(1)
    if language_id == "html" and name.lower() in _HTML_VOID:
        return None
    return f"</{name}>"


def install(api: ForgeAPI) -> None:
    def on_char(editor: EditorHandle, char: str) -> None:
        if char != ">" or not api.setting("autoclose", True):
            return
        widget = editor.widget
        line, index = widget.getCursorPosition()
        before = str(widget.text(line))[:index]
        tag = closing_tag(before, editor.language_id)
        if tag is None:
            return
        data = tag.encode("utf-8")
        position = widget.SendScintilla(QsciScintilla.SCI_GETCURRENTPOS)
        widget.SendScintilla(QsciScintilla.SCI_INSERTTEXT, position, data)

    api.on("char_added", on_char)


def toggled(api: ForgeAPI) -> None:
    """The menu check mark is the setting; nothing else to do."""

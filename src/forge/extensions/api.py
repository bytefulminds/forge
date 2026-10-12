"""ForgeAPI: everything a built-in tool (and later a plugin) may use.

Tools import only this module (and forge.extensions.base, forge.core,
forge.themes, PyQt6); a ruff rule forbids forge.ui and forge.editor. That
keeps tools shaped like external plugins, so opening this API to a plugin
library later needs no changes here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtWidgets import QWidget

from forge.core.tasks import run_in_background
from forge.i18n.translator import tr
from forge.themes.theme import Theme

if TYPE_CHECKING:
    from forge.ui.document_tab import DocumentTab

__all__ = ["EditorHandle", "ForgeAPI", "tr"]

_Q = QsciScintilla


class EditorHandle:
    """A stable wrapper around one open document."""

    def __init__(self, tab: DocumentTab) -> None:
        self._tab = tab

    @property
    def widget(self) -> QsciScintilla:
        """The Scintilla widget, for raw ``SendScintilla`` access."""
        return self._tab

    @property
    def title(self) -> str:
        return self._tab.title

    @property
    def path(self) -> Path | None:
        return self._tab.doc.path

    @property
    def language_id(self) -> str:
        return self._tab.language.id

    @property
    def is_large(self) -> bool:
        return self._tab.large_file

    @property
    def is_dirty(self) -> bool:
        return self._tab.is_dirty

    def is_same(self, other: EditorHandle) -> bool:
        return self._tab is other._tab

    def text(self) -> str:
        return str(self._tab.text())

    def set_text(self, text: str) -> None:
        """Replace the whole document as one undo step, keeping the caret line."""
        line, _ = self._tab.getCursorPosition()
        first = self._tab.firstVisibleLine()
        self._tab.beginUndoAction()
        try:
            self._tab.selectAll()
            self._tab.replaceSelectedText(text)
        finally:
            self._tab.endUndoAction()
        self._tab.setCursorPosition(min(line, max(0, self._tab.lines() - 1)), 0)
        self._tab.setFirstVisibleLine(first)

    @property
    def eol(self) -> str:
        """The document's line ending."""
        mode = int(self._tab.SendScintilla(_Q.SCI_GETEOLMODE))
        return {0: "\r\n", 1: "\r"}.get(mode, "\n")

    @property
    def csv_delimiter(self) -> str:
        """The CSV delimiter in use (chosen by the user or detected)."""
        return str(self._tab.csv_delimiter)

    @property
    def csv_delimiter_choice(self) -> str | None:
        """The delimiter the user chose, or ``None`` when it is detected."""
        return self._tab.csv_delimiter_choice

    def set_csv_delimiter(self, delimiter: str | None) -> None:
        self._tab.set_csv_delimiter(delimiter)

    def text_before_caret(self) -> str:
        position = int(self._tab.SendScintilla(_Q.SCI_GETCURRENTPOS))
        return bytes(self._tab.bytes(0, position).data())[:position].decode("utf-8", "replace")

    def has_selection(self) -> bool:
        return bool(self._tab.hasSelectedText())

    def selected_text(self) -> str:
        return str(self._tab.selectedText())

    def replace_selection(self, text: str) -> None:
        self._tab.beginUndoAction()
        try:
            self._tab.replaceSelectedText(text)
        finally:
            self._tab.endUndoAction()

    def replace_selection_and_select(self, text: str, start: int, length: int) -> None:
        """Replace the selection with ``text`` and select ``length`` characters
        of it from character offset ``start`` (one undo step)."""
        tab = self._tab
        origin = int(tab.SendScintilla(_Q.SCI_GETSELECTIONSTART))
        self.replace_selection(text)
        anchor = origin + len(text[:start].encode("utf-8"))
        caret = anchor + len(text[start : start + length].encode("utf-8"))
        tab.SendScintilla(_Q.SCI_SETSEL, anchor, caret)
        tab.setFocus()

    def text_around_selection(self, count: int) -> tuple[str, str]:
        """Up to ``count`` bytes of text right before and right after the selection."""
        tab = self._tab
        start = int(tab.SendScintilla(_Q.SCI_GETSELECTIONSTART))
        end = int(tab.SendScintilla(_Q.SCI_GETSELECTIONEND))
        length = int(tab.SendScintilla(_Q.SCI_GETLENGTH))
        first, last = max(0, start - count), min(length, end + count)
        # QScintilla's bytes() adds a trailing NUL: keep only the requested range.
        before = tab.bytes(first, start).data()[: start - first]
        after = tab.bytes(end, last).data()[: last - end]
        return before.decode("utf-8", "replace"), after.decode("utf-8", "replace")

    def extend_selection(self, before: int, after: int) -> None:
        """Grow the selection by ``before`` bytes to the left and ``after`` to the right."""
        tab = self._tab
        start = int(tab.SendScintilla(_Q.SCI_GETSELECTIONSTART))
        end = int(tab.SendScintilla(_Q.SCI_GETSELECTIONEND))
        tab.SendScintilla(_Q.SCI_SETSEL, start - before, end + after)

    def selected_line_range(self) -> tuple[int, int]:
        """0-based first and last line touched by the selection or the caret.

        A selection that ends at the very start of a line does not include it."""
        tab = self._tab
        if not tab.hasSelectedText():
            line, _ = tab.getCursorPosition()
            return int(line), int(line)
        first, _, last, last_column = tab.getSelection()
        if last > first and last_column == 0:
            last -= 1
        return int(first), int(last)

    def line_texts(self, first: int, last: int) -> list[str]:
        """The text of lines ``first`` to ``last`` (0-based) without line endings."""
        return [str(self._tab.text(i)).rstrip("\r\n") for i in range(first, last + 1)]

    def replace_lines(self, first: int, last: int, lines: list[str]) -> None:
        """Replace lines ``first`` to ``last`` (0-based, without their final line
        ending) by ``lines`` as one undo step and select the result."""
        tab = self._tab
        start = int(tab.SendScintilla(_Q.SCI_POSITIONFROMLINE, first))
        end = int(tab.SendScintilla(_Q.SCI_GETLINEENDPOSITION, last))
        eol = self.eol
        tab.SendScintilla(_Q.SCI_SETSEL, start, end)
        self.replace_selection(eol.join(lines))
        caret = int(tab.SendScintilla(_Q.SCI_GETCURRENTPOS))
        tab.SendScintilla(_Q.SCI_SETSEL, start, caret)
        tab.setFocus()

    def selection_start_line(self) -> int:
        """1-based line where the selection (or caret) starts."""
        line, _, _, _ = self._tab.getSelection()
        if line < 0:
            line, _ = self._tab.getCursorPosition()
        return int(line) + 1

    def set_language(self, language_id: str) -> None:
        from forge.editor.lexers import language_by_id

        self._tab.set_language(language_by_id(language_id))

    def go_to(self, line: int, column: int = 1) -> None:
        """Move the caret to 1-based ``line`` and ``column`` and center it."""
        last = max(0, self._tab.lines() - 1)
        target = max(0, min(last, line - 1))
        self._tab.setCursorPosition(target, max(0, column - 1))
        self._tab.SendScintilla(_Q.SCI_ENSUREVISIBLEENFORCEPOLICY, target)
        self._tab.SendScintilla(_Q.SCI_VERTICALCENTRECARET)
        self._tab.setFocus()

    def select(self, line: int, column: int, length: int) -> None:
        """Select ``length`` characters from 1-based ``line``/``column``."""
        self.go_to(line, column)
        self._tab.setSelection(line - 1, column - 1, line - 1, column - 1 + length)

    def indent_unit(self) -> str:
        if self._tab.indentationsUseTabs():
            return "\t"
        return " " * int(self._tab.tabWidth())


class ForgeAPI:
    """Facade handed to every tool. ``host`` is the main window."""

    def __init__(self, host: Any, extension_id: str) -> None:
        self._host = host
        self.extension_id = extension_id

    # Text and UI basics ------------------------------------------------------

    tr = staticmethod(tr)

    @property
    def window(self) -> QWidget:
        """Parent for dialogs."""
        widget: QWidget = self._host
        return widget

    @property
    def theme(self) -> Theme:
        theme: Theme = self._host.theme
        return theme

    def status(self, message: str, timeout_ms: int = 4000) -> None:
        self._host.status.showMessage(message, timeout_ms)

    def notify(
        self,
        message: str,
        kind: str = "info",
        actions: list[tuple[str, Callable[[], object]]] | None = None,
    ) -> None:
        """Show a notice above the status bar for the active document."""
        self._host.show_tool_notice(message, kind, actions or [])

    def show_error_at(self, editor: EditorHandle, message: str, line: int, column: int) -> None:
        """Jump to an error position and explain it in a notice."""
        editor.go_to(line, column)
        self.notify(
            message,
            "warning",
            [(tr("Go to Error"), lambda: editor.go_to(line, column))],
        )

    # Documents ---------------------------------------------------------------

    def active_editor(self) -> EditorHandle | None:
        tab = self._host.current_tab()
        return EditorHandle(tab) if tab is not None else None

    def editors(self) -> list[EditorHandle]:
        return [EditorHandle(tab) for tab in self._host.all_tabs()]

    def new_document(self, text: str = "", language_id: str = "text") -> EditorHandle:
        tab = self._host.new_document()
        handle = EditorHandle(tab)
        tab.setText(text)
        handle.set_language(language_id)
        return handle

    def open_file(self, path: Path) -> EditorHandle | None:
        tab = self._host.open_path(path)
        return EditorHandle(tab) if tab is not None else None

    def dialog_dir(self) -> Path:
        directory: Path = self._host.dialog_dir()
        return directory

    # Panels and tabs ---------------------------------------------------------

    def confirm(self, title: str, text: str) -> bool:
        """Ask a Yes / No question in Forge's dialog style; Yes returns True."""
        from forge.ui import message_box

        answer = message_box.question(self.window, title, text)
        return answer == message_box.Button.Yes

    def choose_folder(self, title: str, start: str) -> str:
        """A folder picked by the user ("" when cancelled), in Forge's dialog style."""
        from forge.ui.file_dialogs import get_folder

        return get_folder(self.window, title, start)

    def panel(self, panel_id: str, title: str, factory: Callable[[], QWidget]) -> QWidget:
        """Show (creating once) a dock panel below the editor and return its widget."""
        widget: QWidget = self._host.show_panel(panel_id, title, factory)
        return widget

    def add_tab(self, widget: QWidget, title: str) -> None:
        """Show a tool view (such as a comparison) as a closable tab."""
        self._host.add_tool_tab(widget, title)

    def set_document_view(self, editor: EditorHandle, mode: str) -> None:
        """Show a document as "text", "split" (text and rendered view) or "preview"."""
        self._host.set_view_mode(editor.widget, mode)

    def create_viewer(self) -> QsciScintilla:
        """A read-only editor widget styled like Forge's editors."""
        viewer: QsciScintilla = self._host.create_viewer()
        return viewer

    # Events, settings and background work -----------------------------------

    def on(self, event: str, callback: Callable[..., None]) -> None:
        """Subscribe to "tab_changed" (editor) or "char_added" (editor, char)."""
        self._host.extension_events.subscribe(event, callback, self.extension_id)

    def setting(self, key: str, default: object = None) -> object:
        return self._host.settings.tools.get(self.extension_id, {}).get(key, default)

    def set_setting(self, key: str, value: object) -> None:
        self._host.settings.tools.setdefault(self.extension_id, {})[key] = value
        self._host.settings.save()

    def run_in_background(
        self,
        fn: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        run_in_background(fn, on_done, on_error)

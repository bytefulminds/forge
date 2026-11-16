"""JSON path query window: type a path, the matches are selected in the code."""

from __future__ import annotations

import json

from PyQt6 import sip
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from forge.extensions.api import EditorHandle, ForgeAPI, tr
from forge.tools.json_tool.convert import Match, QueryError, path_text, query

QUERY_DELAY_MS = 150


class QueryDialog:
    """A small window that stays open next to the code while you query."""

    def __init__(self, api: ForgeAPI, editor: EditorHandle) -> None:
        self.api = api
        self.editor = editor
        self.matches: list[Match] = []
        self.dialog = api.framed_dialog(tr("JSON Path Query"), resizable=True)
        self.dialog.setModal(False)
        self.dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        hint = QLabel(tr("Examples: $.items[0].name, items[*].price, $..id, $['a key']"), body)
        hint.setObjectName("resultNote")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.field = QLineEdit(body)
        self.field.setPlaceholderText("$.items[*].name")
        self.field.setClearButtonEnabled(True)
        layout.addWidget(self.field)
        self.result = QLabel(body)
        self.result.setObjectName("resultNote")
        layout.addWidget(self.result)
        self.list = QListWidget(body)
        self.list.setUniformItemSizes(True)
        layout.addWidget(self.list, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, body)
        buttons.rejected.connect(self.dialog.close)
        layout.addWidget(buttons)

        self.timer = QTimer(self.dialog)
        self.timer.setSingleShot(True)
        self.timer.setInterval(QUERY_DELAY_MS)
        self.timer.timeout.connect(self.run)
        self.field.textChanged.connect(lambda _text: self.timer.start())
        self.field.returnPressed.connect(self.run)
        self.list.currentRowChanged.connect(self._pick)
        self.dialog.resize(440, 380)
        # Keep this object alive as long as its window (slots hold weak references).
        self.dialog.setProperty("forgeQuery", self)

    def show(self) -> None:
        self.dialog.show()
        window = self.api.window
        corner = window.mapToGlobal(QPoint(window.width(), 0))
        self.dialog.move(corner.x() - self.dialog.width() - 24, corner.y() + 96)
        self.field.setFocus()

    def _editor_alive(self) -> bool:
        return not sip.isdeleted(self.editor.widget)

    def run(self) -> None:
        self.timer.stop()
        expression = self.field.text().strip()
        self.list.clear()
        self.matches = []
        if not expression or not self._editor_alive():
            self.result.setText("")
            return
        try:
            self.matches = query(self.editor.text(), expression)
        except json.JSONDecodeError as error:
            self.result.setText(
                tr(
                    "Invalid JSON at line {line}, column {column}.",
                    line=error.lineno,
                    column=error.colno,
                )
            )
            return
        except QueryError as error:
            self.result.setText(tr("Not a path: {error}", error=str(error)))
            return
        count = len(self.matches)
        self.result.setText(
            tr("No matches.") if count == 0
            else tr("1 match") if count == 1
            else tr("{count} matches", count=count)
        )  # fmt: skip
        self.list.blockSignals(True)
        for match in self.matches:
            item = QListWidgetItem(f"{path_text(match.path)}  =  {match.preview}")
            item.setToolTip(match.preview)
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self.matches:
            self.editor.select_ranges([(m.start, m.end) for m in self.matches])

    def _pick(self, row: int) -> None:
        if 0 <= row < len(self.matches) and self._editor_alive():
            match = self.matches[row]
            self.editor.select_ranges([(match.start, match.end)])


def open_query(api: ForgeAPI, editor: EditorHandle) -> QueryDialog:
    window = QueryDialog(api, editor)
    if editor.has_selection():
        selected = editor.selected_text().strip()
        if selected.startswith("$") and "\n" not in selected:
            window.field.setText(selected)
    window.show()
    return window

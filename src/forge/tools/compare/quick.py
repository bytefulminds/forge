"""Quick Diff: paste two texts side by side and compare them in a tab."""

from __future__ import annotations

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI, tr
from forge.tools.compare.actions import show_comparison


class QuickDiff:
    def __init__(self, api: ForgeAPI, left: str = "", right: str = "") -> None:
        self.api = api
        self.dialog = api.framed_dialog(tr("Quick Diff"), resizable=True)
        self.dialog.setProperty("forgeTool", self)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        hint = QLabel(tr("Paste the old text on the left and the new text on the right."), body)
        hint.setObjectName("resultNote")
        layout.addWidget(hint)

        self.left = self._pane(left)
        self.right = self._pane(right)
        splitter = QSplitter(Qt.Orientation.Horizontal, body)
        splitter.addWidget(self._titled(tr("Old"), self.left, body, lambda: self._paste(self.left)))
        splitter.addWidget(
            self._titled(tr("New"), self.right, body, lambda: self._paste(self.right))
        )
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(14)
        layout.addWidget(splitter, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, body
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.setText(tr("Compare"))
        buttons.accepted.connect(self.dialog.accept)
        buttons.rejected.connect(self.dialog.reject)
        layout.addWidget(buttons)
        self.dialog.resize(900, 560)

    def _pane(self, text: str) -> QsciScintilla:
        pane = self.api.create_viewer()
        pane.setReadOnly(False)
        pane.setText(text)
        return pane

    @staticmethod
    def _titled(title: str, pane: QWidget, parent: QWidget, paste: object) -> QWidget:
        box = QWidget(parent)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        label = QLabel(title, box)
        label.setObjectName("paneTitle")
        row.addWidget(label, 1)
        button = QPushButton(tr("Paste"), box)
        button.clicked.connect(paste)  # type: ignore[arg-type]
        row.addWidget(button)
        layout.addLayout(row)
        pane.setParent(box)
        layout.addWidget(pane, 1)
        return box

    def _paste(self, pane: QsciScintilla) -> None:
        pane.setText(self.api.clipboard_text())

    def texts(self) -> tuple[str, str]:
        return str(self.left.text()), str(self.right.text())

    def exec(self) -> int:
        return self.dialog.exec()


def open_quick_diff(api: ForgeAPI) -> None:
    editor = api.active_editor()
    right = editor.selected_text() if editor is not None and editor.has_selection() else ""
    window = QuickDiff(api, "", right)
    if window.exec() != window.dialog.DialogCode.Accepted:
        return
    left, right = window.texts()
    if not left and not right:
        return
    show_comparison(api, left, right, tr("Old"), tr("New"), tr("Quick Diff"))

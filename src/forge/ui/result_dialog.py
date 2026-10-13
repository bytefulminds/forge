"""A Forge-framed window listing labelled values, each with a copy button
(hashes, date conversions, decoded tokens)."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forge.i18n.translator import tr
from forge.ui import file_dialogs
from forge.ui.framed_dialog import FramedDialog
from forge.ui.icons import ICON_SIZE, themed_icon


def copy_to_clipboard(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)


def copy_button(parent: QWidget, text: Callable[[], str]) -> QToolButton:
    """A small copy icon button that copies ``text()`` when clicked."""
    button = QToolButton(parent)
    button.setObjectName("docToolButton")
    button.setToolTip(tr("Copy"))
    button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
    theme = file_dialogs.current_theme
    if theme is not None:
        button.setIcon(themed_icon("copy", theme.text_muted, theme.text, theme.text_disabled))
    else:
        button.setText(tr("Copy"))
    button.clicked.connect(lambda: copy_to_clipboard(text()))
    return button


class ResultDialog(FramedDialog):
    def __init__(
        self,
        title: str,
        rows: list[tuple[str, str]],
        note: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent, resizable=True)
        self.setObjectName("resultDialog")
        self.rows = rows
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(12)
        if note:
            label = QLabel(note, self.body)
            label.setObjectName("resultNote")
            label.setWordWrap(True)
            layout.addWidget(label)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        mono = QFont("JetBrains Mono")
        self.fields: list[QLineEdit | QPlainTextEdit] = []
        for row, (name, value) in enumerate(rows):
            label = QLabel(name, self.body)
            field: QLineEdit | QPlainTextEdit
            if "\n" in value or len(value) > 140:
                field = QPlainTextEdit(value, self.body)
                field.setMinimumHeight(110)
                label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            else:
                field = QLineEdit(value, self.body)
                field.setCursorPosition(0)
                label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            field.setReadOnly(True)
            field.setFont(mono)
            self.fields.append(field)
            copy = copy_button(self.body, partial(str, value))
            grid.addWidget(label, row, 0)
            grid.addWidget(field, row, 1)
            grid.addWidget(copy, row, 2)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self.body)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(640, self.sizeHint().height())

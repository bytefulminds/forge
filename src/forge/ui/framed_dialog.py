"""Dialogs in Forge's own frame, matching the main window on every platform.

``FramedDialog`` is a frameless QDialog with a small Forge title bar (title,
close button, drag to move) and a 1 px border. Subclasses put their content
in ``self.body``.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QMouseEvent, QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from forge.ui.title_bar import IS_MAC, WindowButton

DIALOG_TITLE_HEIGHT = 34


class DialogTitleBar(QWidget):
    def __init__(self, dialog: QDialog) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._drag_offset: QPoint | None = None
        self.setObjectName("dialogTitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(DIALOG_TITLE_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.close_button = WindowButton("close", self)
        self.close_button.setFixedSize(42, DIALOG_TITLE_HEIGHT)
        self.close_button.clicked.connect(dialog.reject)
        self.title = QLabel(dialog.windowTitle(), self)
        self.title.setObjectName("dialogTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addSpacing(self.close_button.width())  # keeps the title centered
        layout.addWidget(self.title, 1)
        layout.addWidget(self.close_button)
        dialog.windowTitleChanged.connect(self.title.setText)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            handle = self._dialog.windowHandle()
            if not IS_MAC and handle is not None and handle.startSystemMove():
                event.accept()
                return
            self._drag_offset = (
                event.globalPosition().toPoint() - self._dialog.frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if (
            event is not None
            and self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._dialog.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class FramedDialog(QDialog):
    def __init__(self, title: str, parent: QWidget | None = None, resizable: bool = False) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle(title)
        self.setModal(True)

        frame = QFrame(self)
        frame.setObjectName("dialogFrame")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(1, 1, 1, 1)  # the frame's border
        layout.setSpacing(0)
        self.title_bar = DialogTitleBar(self)
        layout.addWidget(self.title_bar)
        self.body = QWidget(frame)
        self.body.setObjectName("dialogBody")
        layout.addWidget(self.body, 1)
        if resizable:
            grip_row = QHBoxLayout()
            grip_row.setContentsMargins(0, 0, 0, 0)
            grip_row.addStretch(1)
            grip_row.addWidget(QSizeGrip(frame), 0, Qt.AlignmentFlag.AlignBottom)
            layout.addLayout(grip_row)

    def showEvent(self, event: QShowEvent | None) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        window = parent.window() if parent is not None else None
        if window is not None:
            center = window.frameGeometry().center()
            geometry = self.frameGeometry()
            geometry.moveCenter(center)
            self.move(geometry.topLeft())

"""Questions and messages in Forge's own frame (like ``QMessageBox``'s static
functions, same arguments and return values)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from forge.ui import file_dialogs
from forge.ui.framed_dialog import FramedDialog
from forge.ui.icons import themed_icon

Button = QMessageBox.StandardButton
_ICON_SIZE = 28
# Answer when the box is closed with Esc or the close button, in this order.
_ESCAPE_ORDER = (Button.Cancel, Button.No, Button.Close, Button.Ok, Button.Abort)


class FramedMessageBox(FramedDialog):
    def __init__(
        self,
        kind: str,
        title: str,
        text: str,
        buttons: Button,
        default: Button = Button.NoButton,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self.setObjectName("messageBox")
        self.answer = Button.NoButton
        self._buttons = buttons

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(16)
        row = QHBoxLayout()
        row.setSpacing(14)
        icon = self._icon(kind)
        if icon is not None:
            row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        self.label = QLabel(text, self.body)
        self.label.setObjectName("messageText")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.AutoText)
        self.label.setOpenExternalLinks(True)
        self.label.setMinimumWidth(320)
        self.label.setMaximumWidth(460)
        row.addWidget(self.label, 1)
        layout.addLayout(row)

        box = QDialogButtonBox(self.body)
        for value in Button:
            if value != Button.NoButton and buttons & value:
                button = box.addButton(QDialogButtonBox.StandardButton(value.value))
                if button is None:
                    continue
                button.clicked.connect(lambda _c=False, v=value: self._answer(v))
                if value == default:
                    button.setDefault(True)
                    button.setFocus()
        if default == Button.NoButton:
            first = box.buttons()[0] if box.buttons() else None
            if isinstance(first, QPushButton):
                first.setDefault(True)
        layout.addWidget(box)
        self.adjustSize()

    def _icon(self, kind: str) -> QLabel | None:
        theme = file_dialogs.current_theme
        names = {
            "question": "circle-help",
            "warning": "triangle-alert",
            "information": "info",
            "critical": "circle-x",
        }
        if theme is None or kind not in names:
            return None
        color = {"warning": theme.warning, "critical": theme.error}.get(kind, theme.accent)
        label = QLabel(self.body)
        label.setObjectName("messageIcon")
        label.setPixmap(themed_icon(names[kind], color, color, color).pixmap(_ICON_SIZE))
        return label

    def _answer(self, value: Button) -> None:
        self.answer = value
        self.accept()

    def reject(self) -> None:
        for value in _ESCAPE_ORDER:
            if self._buttons & value:
                self.answer = value
                break
        super().reject()


def _show(
    kind: str,
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: Button,
    default: Button,
) -> Button:
    box = FramedMessageBox(kind, title, text, buttons, default, parent)
    box.exec()
    return box.answer


def question(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: Button = Button.Yes | Button.No,
    default: Button = Button.NoButton,
) -> Button:
    return _show("question", parent, title, text, buttons, default)


def warning(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: Button = Button.Ok,
    default: Button = Button.NoButton,
) -> Button:
    return _show("warning", parent, title, text, buttons, default)


def information(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: Button = Button.Ok,
    default: Button = Button.NoButton,
) -> Button:
    return _show("information", parent, title, text, buttons, default)


def critical(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: Button = Button.Ok,
    default: Button = Button.NoButton,
) -> Button:
    return _show("critical", parent, title, text, buttons, default)


def about(parent: QWidget | None, title: str, text: str) -> None:
    _show("about", parent, title, text, Button.Ok, Button.Ok)

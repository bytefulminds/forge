"""A slim, non-modal bar above the editor for things like external changes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QWidget

from forge.i18n.translator import tr


@dataclass
class Notice:
    kind: str  # "info" or "warning"; selects the accent color
    message: str
    actions: list[tuple[str, Callable[[], object]]] = field(default_factory=list)


class NoticeBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("noticeBar")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 6, 6, 6)
        self._layout.setSpacing(8)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self._layout.addWidget(self.label, 1)
        self._buttons: list[QPushButton] = []
        self.dismiss = QToolButton(self)
        self.dismiss.setObjectName("noticeDismiss")
        self.dismiss.setText("×")
        self.dismiss.setToolTip(tr("Dismiss"))
        self.dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self._layout.addWidget(self.dismiss)
        self._on_dismiss: Callable[[], None] | None = None
        self.dismiss.clicked.connect(self._dismissed)
        self.hide()

    def show_notice(self, notice: Notice | None, on_dismiss: Callable[[], None]) -> None:
        for button in self._buttons:
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons = []
        if notice is None:
            self.hide()
            return
        self.setProperty("kind", notice.kind)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.label.setText(notice.message)
        for index, (text, callback) in enumerate(notice.actions):
            button = QPushButton(text, self)
            button.setProperty("primary", "true" if index == 0 else "false")
            button.clicked.connect(lambda _c=False, cb=callback: cb())
            self._layout.insertWidget(self._layout.count() - 1, button)
            self._buttons.append(button)
        self._on_dismiss = on_dismiss
        self.show()

    @property
    def buttons(self) -> list[QPushButton]:
        return list(self._buttons)

    def _dismissed(self) -> None:
        if self._on_dismiss is not None:
            self._on_dismiss()

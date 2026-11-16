"""Small widgets shared by the tool windows."""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget


class InfoHint(QWidget):
    """An info icon and a one-line tip, cut off with "..." when it does not fit;
    hovering shows the whole tip."""

    def __init__(self, icon: QIcon, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("infoHint")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(6)
        self.icon = QLabel(self)
        self.icon.setPixmap(icon.pixmap(QSize(14, 14), self.devicePixelRatioF()))
        layout.addWidget(self.icon)
        self.label = QLabel(self)
        self.label.setObjectName("resultNote")
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.label, 1)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.text = ""

    def set_text(self, text: str) -> None:
        self.text = text
        self.setToolTip(text)
        self._elide()

    def _elide(self) -> None:
        width = max(0, self.label.width())
        self.label.setText(
            self.label.fontMetrics().elidedText(self.text, Qt.TextElideMode.ElideRight, width)
        )

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._elide()

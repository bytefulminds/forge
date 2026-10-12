"""Go to line (Ctrl+G in Notepad++)."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from forge.i18n.translator import tr


class GoToLineDialog(QDialog):
    def __init__(self, current: int, last: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Go to Line"))
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel(tr("Line number (1 - {last}):", last=last), self))
        self.spin = QSpinBox(self)
        self.spin.setRange(1, max(1, last))
        self.spin.setValue(max(1, min(current, last)))
        self.spin.selectAll()
        layout.addWidget(self.spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Go"))
            ok.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addSpacing(6)
        layout.addWidget(buttons)
        self.setMinimumWidth(300)

    @property
    def line(self) -> int:
        return int(self.spin.value())

"""Language menu: a filter field above a short, scrollable list of languages."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from forge.editor.lexers import PLAIN_TEXT, Language
from forge.i18n.translator import tr

VISIBLE_ROWS = 10
_ROLE = Qt.ItemDataRole.UserRole


def language_label(language: Language) -> str:
    return tr("Normal text") if language is PLAIN_TEXT else language.name


class LanguagePicker(QWidget):
    language_chosen = pyqtSignal(object)

    def __init__(self, languages: list[Language], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("languagePicker")
        self._current: Language | None = None

        self.filter = QLineEdit(self)
        self.filter.setPlaceholderText(tr("Filter languages"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.apply_filter)
        self.filter.installEventFilter(self)

        self.list = QListWidget(self)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setUniformItemSizes(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._choose_item)
        for language in languages:
            item = QListWidgetItem(language_label(language))
            item.setData(_ROLE, language)
            self.list.addItem(item)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.addWidget(self.filter)
        layout.addWidget(self.list)
        self.setMinimumWidth(220)
        self._fit_rows()

    def _fit_rows(self) -> None:
        # Measured after the stylesheet is applied (item padding changes the row height).
        self.list.ensurePolished()
        row = self.list.sizeHintForRow(0) if self.list.count() else 24
        self.list.setFixedHeight(row * VISIBLE_ROWS + 2 * self.list.frameWidth() + 2)

    def set_current(self, language: Language) -> None:
        self._current = language
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None:
                font = item.font()
                font.setBold(item.data(_ROLE) is language)
                item.setFont(font)

    def reset(self) -> None:
        """Called each time the menu opens."""
        self._fit_rows()
        self.filter.clear()
        self.apply_filter("")
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None and item.data(_ROLE) is self._current:
                self.list.setCurrentItem(item)
                self.list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
        self.filter.setFocus()

    def visible_items(self) -> list[QListWidgetItem]:
        items = (self.list.item(i) for i in range(self.list.count()))
        return [item for item in items if item is not None and not item.isHidden()]

    def apply_filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None:
                item.setHidden(bool(needle) and needle not in item.text().casefold())
        visible = self.visible_items()
        if needle and visible:
            self.list.setCurrentItem(visible[0])

    def _move(self, step: int) -> None:
        visible = self.visible_items()
        if not visible:
            return
        current = self.list.currentItem()
        index = visible.index(current) if current in visible else -1
        index = max(0, min(len(visible) - 1, index + step))
        self.list.setCurrentItem(visible[index])

    def choose_current(self) -> None:
        item = self.list.currentItem()
        if item is not None and not item.isHidden():
            self._choose_item(item)

    def _choose_item(self, item: QListWidgetItem) -> None:
        self.language_chosen.emit(item.data(_ROLE))

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        is_key_press = isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress
        if obj is self.filter and is_key_press and isinstance(event, QKeyEvent):
            key = event.key()
            if key == Qt.Key.Key_Down:
                self._move(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.choose_current()
                return True
        return super().eventFilter(obj, event)


class LanguageMenu(QMenu):
    """Menu holding a LanguagePicker. Used by the menu bar and the status bar."""

    language_chosen = pyqtSignal(object)

    def __init__(self, title: str, languages: list[Language], parent: QWidget | None = None):
        super().__init__(title, parent)
        self.picker = LanguagePicker(languages, self)
        action = QWidgetAction(self)
        action.setDefaultWidget(self.picker)
        self.addAction(action)
        self.picker.language_chosen.connect(self._on_chosen)
        self.aboutToShow.connect(self._prepare)

    def _prepare(self) -> None:
        self.picker.reset()
        self.picker.adjustSize()
        self.adjustSize()

    def set_current(self, language: Language) -> None:
        self.picker.set_current(language)

    def _on_chosen(self, language: Language) -> None:
        self.close()
        self.language_chosen.emit(language)

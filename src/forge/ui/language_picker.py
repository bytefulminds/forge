"""Language menu: a filter field above a short, scrollable list of languages.

Filtering goes through a QSortFilterProxyModel, so rows that do not match are
removed from the view's model instead of hidden. Hidden rows confuse Qt's
accessibility layer on macOS ("QAccessibleList::child: Invalid index").
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEvent,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QFont, QKeyEvent, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLineEdit,
    QListView,
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

        self._model = QStandardItemModel(self)
        for language in languages:
            item = QStandardItem(language_label(language))
            item.setData(language, _ROLE)
            item.setEditable(False)
            self._model.appendRow(item)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.list = QListView(self)
        self.list.setModel(self._proxy)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setUniformItemSizes(True)
        self.list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.clicked.connect(self._choose_index)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.addWidget(self.filter)
        layout.addWidget(self.list)
        self.setMinimumWidth(220)
        self._fit_rows()

    @property
    def total_count(self) -> int:
        return int(self._model.rowCount())

    def _fit_rows(self) -> None:
        # Measured after the stylesheet is applied (item padding changes the row height).
        self.list.ensurePolished()
        row = self.list.sizeHintForRow(0) if self._proxy.rowCount() else 24
        self.list.setFixedHeight(row * VISIBLE_ROWS + 2 * self.list.frameWidth() + 2)

    def set_current(self, language: Language) -> None:
        self._current = language
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item is not None:
                font = QFont(item.font())
                font.setBold(item.data(_ROLE) is language)
                item.setFont(font)

    def reset(self) -> None:
        """Called each time the menu opens."""
        self.filter.clear()
        self.apply_filter("")
        self._fit_rows()
        for row in range(self._proxy.rowCount()):
            index = self._proxy.index(row, 0)
            if index.data(_ROLE) is self._current:
                self.list.setCurrentIndex(index)
                self.list.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
                break
        self.filter.setFocus()

    def visible_labels(self) -> list[str]:
        return [str(self._proxy.index(r, 0).data()) for r in range(self._proxy.rowCount())]

    def apply_filter(self, text: str) -> None:
        self._proxy.setFilterFixedString(text.strip())
        if text.strip() and self._proxy.rowCount():
            self.list.setCurrentIndex(self._proxy.index(0, 0))

    def _move(self, step: int) -> None:
        rows = self._proxy.rowCount()
        if not rows:
            return
        current = self.list.currentIndex()
        row = current.row() if current.isValid() else -1
        row = max(0, min(rows - 1, row + step))
        self.list.setCurrentIndex(self._proxy.index(row, 0))

    def choose_current(self) -> None:
        index = self.list.currentIndex()
        if index.isValid():
            self._choose_index(index)

    def _choose_index(self, index: QModelIndex) -> None:
        self.language_chosen.emit(index.data(_ROLE))

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

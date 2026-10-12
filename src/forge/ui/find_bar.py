"""Find and replace bar below the editor (non-modal, Notepad++ shortcuts).

Typing searches incrementally from where the caret was when the bar opened and
highlights every match. Enter / Shift+Enter (or F3 / Shift+F3) step through
matches, Escape closes the bar and removes the highlights.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QWidget,
)

from forge.editor import search
from forge.editor.search import InvalidPattern, SearchOptions
from forge.i18n.translator import tr
from forge.ui.document_tab import DocumentTab

# More matches than this are counted as "N+" and not all highlighted.
MAX_MATCHES = 5000
DEBOUNCE_MS = 120


def _option(text: str, tooltip: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName("findOption")
    button.setText(text)
    button.setToolTip(tooltip)
    button.setCheckable(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button


def _icon_button(text: str, tooltip: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName("findNav")
    button.setText(text)
    button.setToolTip(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button


class FindBar(QFrame):
    def __init__(
        self,
        current_tab: Callable[[], DocumentTab | None],
        show_message: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("findBar")
        self._current_tab = current_tab
        self._show_message = show_message
        self._tab: DocumentTab | None = None
        self._anchor = 0

        self.find_edit = QLineEdit(self)
        self.find_edit.setPlaceholderText(tr("Find"))
        self.find_edit.setClearButtonEnabled(True)
        self.replace_edit = QLineEdit(self)
        self.replace_edit.setPlaceholderText(tr("Replace with"))
        self.replace_edit.setClearButtonEnabled(True)

        self.match_case = _option("Aa", tr("Match case"))
        self.whole_word = _option("W", tr("Match whole word only"))
        self.regex = _option(".*", tr("Regular expression"))
        self.count = QLabel(self)
        self.count.setObjectName("findCount")
        self.count.setMinimumWidth(90)
        self.previous = _icon_button("↑", tr("Find Previous (Shift+Enter)"))
        self.next = _icon_button("↓", tr("Find Next (Enter)"))
        self.close_button = _icon_button("×", tr("Close (Esc)"))
        self.replace_button = QPushButton(tr("Replace"), self)
        self.replace_all_button = QPushButton(tr("Replace All"), self)

        top = QHBoxLayout()
        top.setSpacing(4)
        for widget in (self.match_case, self.whole_word, self.regex):
            top.addWidget(widget)
        top.addSpacing(6)
        top.addWidget(self.count)
        top.addWidget(self.previous)
        top.addWidget(self.next)
        top.addStretch(1)
        top.addWidget(self.close_button)
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addWidget(self.replace_button)
        bottom.addWidget(self.replace_all_button)
        bottom.addStretch(1)

        grid = QGridLayout(self)
        grid.setContentsMargins(10, 6, 8, 6)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(self.find_edit, 0, 0)
        grid.addLayout(top, 0, 1)
        grid.addWidget(self.replace_edit, 1, 0)
        grid.addLayout(bottom, 1, 1)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)
        self._replace_widgets: tuple[QWidget, ...] = (
            self.replace_edit,
            self.replace_button,
            self.replace_all_button,
        )

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(lambda: self.refresh(move=self._move_on_refresh))
        self._move_on_refresh = False

        self.find_edit.textChanged.connect(lambda _t: self._schedule(move=True))
        for option in (self.match_case, self.whole_word, self.regex):
            option.toggled.connect(lambda _c: self._schedule(move=True))
        self.next.clicked.connect(self.find_next)
        self.previous.clicked.connect(self.find_previous)
        self.close_button.clicked.connect(self.close_bar)
        self.replace_button.clicked.connect(self.replace_one)
        self.replace_all_button.clicked.connect(self.replace_everything)
        self.find_edit.installEventFilter(self)
        self.replace_edit.installEventFilter(self)
        self.hide()

    # Public API -------------------------------------------------------------

    @property
    def options(self) -> SearchOptions:
        return SearchOptions(
            match_case=self.match_case.isChecked(),
            whole_word=self.whole_word.isChecked(),
            regex=self.regex.isChecked(),
        )

    @property
    def replace_mode(self) -> bool:
        return self.replace_edit.isVisible()

    def open_bar(self, replace: bool = False) -> None:
        tab = self._current_tab()
        for widget in self._replace_widgets:
            widget.setVisible(replace)
        if tab is not None:
            selected = tab.selectedText()
            if selected and "\n" not in selected and "\r" not in selected:
                self.find_edit.blockSignals(True)
                self.find_edit.setText(selected)
                self.find_edit.blockSignals(False)
            self._anchor = int(tab.SendScintilla(tab.SCI_GETSELECTIONSTART))
        self.show()
        self.find_edit.setFocus()
        self.find_edit.selectAll()
        self.attach(tab)
        self.refresh(move=False)

    def close_bar(self) -> None:
        if self._tab is not None:
            search.clear_highlight(self._tab)
            self._tab.setFocus()
        self.hide()

    def attach(self, tab: DocumentTab | None) -> None:
        """Follow the active tab: move highlights from the old tab to the new one."""
        if tab is self._tab:
            return
        if self._tab is not None:
            with contextlib.suppress(RuntimeError):
                search.clear_highlight(self._tab)
            # The old tab may already be closed (RuntimeError) or not connected.
            with contextlib.suppress(TypeError, RuntimeError):
                self._tab.textChanged.disconnect(self._on_text_changed)
        self._tab = tab
        if tab is not None:
            tab.textChanged.connect(self._on_text_changed)
        if self.isVisible():
            self.refresh(move=False)

    def find_next(self) -> None:
        self._step(forward=True)

    def find_previous(self) -> None:
        self._step(forward=False)

    def replace_one(self) -> None:
        tab = self._tab
        if tab is None or not self.find_edit.text() or tab.isReadOnly():
            return
        try:
            match = search.replace_current(
                tab, self.find_edit.text(), self.replace_edit.text(), self.options
            )
        except InvalidPattern:
            self._mark_invalid(True)
            return
        if match is None:
            self._show_message(tr("No more matches."))
        self.refresh(move=False)

    def replace_everything(self) -> None:
        tab = self._tab
        if tab is None or not self.find_edit.text() or tab.isReadOnly():
            return
        try:
            count = search.replace_all(
                tab, self.find_edit.text(), self.replace_edit.text(), self.options
            )
        except InvalidPattern:
            self._mark_invalid(True)
            return
        self._show_message(tr("{count} replaced.", count=count))
        self.refresh(move=False)

    # Internals --------------------------------------------------------------

    def _schedule(self, move: bool) -> None:
        self._move_on_refresh = move or self._move_on_refresh
        self._timer.start()

    def _on_text_changed(self) -> None:
        if self.isVisible():
            self._schedule(move=False)

    def _step(self, forward: bool) -> None:
        tab = self._tab or self._current_tab()
        if tab is None:
            return
        if not self.find_edit.text():
            self.open_bar(self.replace_mode)
            return
        self.attach(tab)
        try:
            match = search.find(tab, self.find_edit.text(), self.options, forward=forward)
        except InvalidPattern:
            self._mark_invalid(True)
            return
        if match is None:
            self._show_message(tr("No matches for '{text}'.", text=self.find_edit.text()))
        self.refresh(move=False)

    def refresh(self, move: bool = False) -> None:
        """Recount and re-highlight; with ``move`` jump to the first match from the anchor."""
        self._move_on_refresh = False
        tab = self._tab
        text = self.find_edit.text()
        if tab is None or not text:
            if tab is not None:
                search.clear_highlight(tab)
            self.count.setText("")
            self._mark_invalid(False)
            return
        try:
            matches = search.find_all(tab, text, self.options, limit=MAX_MATCHES + 1)
        except InvalidPattern:
            search.clear_highlight(tab)
            self._mark_invalid(True)
            return
        self._mark_invalid(False)
        if move and matches:
            after = [m for m in matches if m[0] >= self._anchor]
            search.select(tab, (after or matches)[0])
        if tab.large_file:
            search.clear_highlight(tab)  # keep huge documents fast
        else:
            search.highlight(tab, matches[:MAX_MATCHES])
        self._update_count(tab, matches)

    def _update_count(self, tab: DocumentTab, matches: list[search.Match]) -> None:
        if not matches:
            self.count.setText(tr("No results"))
            return
        total = f"{MAX_MATCHES}+" if len(matches) > MAX_MATCHES else str(len(matches))
        selection = (
            int(tab.SendScintilla(tab.SCI_GETSELECTIONSTART)),
            int(tab.SendScintilla(tab.SCI_GETSELECTIONEND)),
        )
        if selection in matches:
            index = matches.index(selection) + 1
            self.count.setText(tr("{current} of {total}", current=index, total=total))
        else:
            self.count.setText(tr("{total} matches", total=total))

    def _mark_invalid(self, invalid: bool) -> None:
        self.find_edit.setProperty("invalid", "true" if invalid else "false")
        style = self.find_edit.style()
        if style is not None:
            style.unpolish(self.find_edit)
            style.polish(self.find_edit)
        if invalid:
            self.count.setText(tr("Invalid expression"))

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if key == Qt.Key.Key_Escape:
                self.close_bar()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if obj is self.replace_edit:
                    self.replace_one()
                else:
                    self._step(forward=not shift)
                return True
        return super().eventFilter(obj, event)

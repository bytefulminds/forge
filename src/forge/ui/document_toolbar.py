"""The toolbar at the top of every document tab.

Left: tools for the document's language (format, validate, Markdown helpers,
...). Right: word wrap and the Text / Split / Preview view buttons. All
buttons are icons with a tooltip.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QMenu, QToolButton, QWidget

from forge.i18n.translator import tr
from forge.themes.theme import Theme
from forge.ui.icons import ICON_SIZE, themed_icon

TEXT = "text"
SPLIT = "split"
PREVIEW = "preview"
VIEW_MODES = (TEXT, SPLIT, PREVIEW)
_MODE_ICONS = {TEXT: "file-text", SPLIT: "columns-2", PREVIEW: "eye"}
_WRAP_ICON = "wrap-text"


@dataclass(frozen=True)
class ToolItem:
    key: str
    icon: str
    tooltip: str
    run: Callable[[], None]
    separator_before: bool = False
    # A dropdown of these actions instead of a click action (checkable options).
    menu: list[QAction] | None = None


class DocumentToolbar(QWidget):
    mode_chosen = pyqtSignal(str)
    wrap_toggled = pyqtSignal(bool)

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("documentToolbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._theme = theme
        self._icons: dict[QToolButton, str] = {}
        self.tool_buttons: dict[str, QToolButton] = {}
        self._tool_widgets: list[QWidget] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(2)
        self._tools = QHBoxLayout()
        self._tools.setContentsMargins(0, 0, 0, 0)
        self._tools.setSpacing(2)
        layout.addLayout(self._tools)
        layout.addStretch(1)

        self.wrap_button = self._button(_WRAP_ICON, tr("Word Wrap"), checkable=True)
        self.wrap_button.toggled.connect(self.wrap_toggled)
        layout.addWidget(self.wrap_button)

        self._mode_separator = self._separator()
        layout.addWidget(self._mode_separator)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.mode_buttons: dict[str, QToolButton] = {}
        tips = {
            TEXT: tr("Show the text only"),
            SPLIT: tr("Show the text and the rendered view side by side"),
            PREVIEW: tr("Show the rendered view only"),
        }
        for mode in VIEW_MODES:
            button = self._button(_MODE_ICONS[mode], tips[mode], checkable=True)
            button.clicked.connect(lambda _c=False, m=mode: self.mode_chosen.emit(m))
            self._group.addButton(button)
            layout.addWidget(button)
            self.mode_buttons[mode] = button
        self.set_modes_visible(False)

    # Building --------------------------------------------------------------------

    def _button(self, icon: str, tooltip: str, checkable: bool = False) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("docToolButton")
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCheckable(checkable)
        button.setAutoRaise(True)
        button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._icons[button] = icon
        self._paint(button)
        return button

    def _separator(self) -> QFrame:
        line = QFrame(self)
        line.setObjectName("docToolSeparator")
        line.setFixedSize(1, 16)
        return line

    def set_tools(self, items: list[ToolItem]) -> None:
        for widget in self._tool_widgets:
            if isinstance(widget, QToolButton):
                self._icons.pop(widget, None)
            widget.deleteLater()
        self._tool_widgets = []
        self.tool_buttons = {}
        for item in items:
            if item.separator_before:
                separator = self._separator()
                self._tools.addWidget(separator)
                self._tool_widgets.append(separator)
            button = self._button(item.icon, item.tooltip)
            if item.menu:
                popup = QMenu(button)
                for action in item.menu:
                    popup.addAction(action)
                button.setMenu(popup)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            else:
                button.clicked.connect(lambda _c=False, run=item.run: run())
            self._tools.addWidget(button)
            self._tool_widgets.append(button)
            self.tool_buttons[item.key] = button

    # State -----------------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        button = self.mode_buttons.get(mode)
        if button is not None:
            button.setChecked(True)

    def set_modes_visible(self, visible: bool) -> None:
        for button in self.mode_buttons.values():
            button.setVisible(visible)
        self._mode_separator.setVisible(visible)

    def set_wrap(self, checked: bool) -> None:
        self.wrap_button.blockSignals(True)
        self.wrap_button.setChecked(checked)
        self.wrap_button.blockSignals(False)

    # Theme -----------------------------------------------------------------------

    def _paint(self, button: QToolButton) -> None:
        theme = self._theme
        button.setIcon(
            themed_icon(self._icons[button], theme.text_muted, theme.text, theme.text_disabled)
        )

    def apply_theme(self, theme: Theme) -> None:
        self._theme = theme
        for button in self._icons:
            self._paint(button)

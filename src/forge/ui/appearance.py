"""Application wide look: bundled fonts, Qt style and theme application."""

from __future__ import annotations

import logging
import sys
from importlib import resources

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QMenuBar,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleHintReturn,
    QStyleOption,
    QWidget,
)

from forge.themes.palette import build_palette
from forge.themes.qss import build_stylesheet
from forge.themes.theme import Theme

log = logging.getLogger(__name__)

UI_FONT_FAMILY = "Inter"
CODE_FONT_FAMILY = "JetBrains Mono"
UI_FONT_PIXEL_SIZE = 13

_FONT_FILES = (
    "Inter-Regular.ttf",
    "Inter-Medium.ttf",
    "Inter-SemiBold.ttf",
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Bold.ttf",
    "JetBrainsMono-Italic.ttf",
)


def default_code_font_size() -> int:
    """Point size that renders the code font at roughly 13 px on each platform."""
    return 13 if sys.platform == "darwin" else 10


def load_bundled_fonts() -> None:
    package = resources.files("forge.resources.fonts")
    for name in _FONT_FILES:
        data = package.joinpath(name).read_bytes()
        if QFontDatabase.addApplicationFontFromData(data) < 0:
            log.warning("Could not load bundled font %s", name)


def ui_font() -> QFont:
    font = QFont(UI_FONT_FAMILY)
    font.setPixelSize(UI_FONT_PIXEL_SIZE)
    return font


class ForgeStyle(QProxyStyle):
    """Fusion with keyboard mnemonic underlines hidden until Alt is pressed."""

    def styleHint(
        self,
        hint: QStyle.StyleHint,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
        returnData: QStyleHintReturn | None = None,
    ) -> int:
        if hint == QStyle.StyleHint.SH_UnderlineShortcut:
            return 0
        return super().styleHint(hint, option, widget, returnData)


def install_style(app: QApplication) -> None:
    app.setStyle(ForgeStyle(QStyleFactory.create("Fusion")))
    app.setFont(ui_font())


def apply_theme(app: QApplication, theme: Theme) -> None:
    # Tells the OS which appearance to use for native parts (macOS title text
    # and traffic lights, native dialogs).
    hints = app.styleHints()
    if hints is not None:
        scheme = Qt.ColorScheme.Dark if theme.is_dark else Qt.ColorScheme.Light
        hints.setColorScheme(scheme)
    app.setPalette(build_palette(theme))
    app.setStyleSheet(build_stylesheet(theme))


def round_popup_menus(root: QMenu | QMenuBar) -> None:
    """Give a menu (and its submenus) a transparent window so QSS can round its corners.

    Must run before the menu is shown for the first time.
    """
    menus: list[QMenu] = [root] if isinstance(root, QMenu) else []
    for action in root.actions():
        sub = action.menu()
        if isinstance(sub, QMenu):
            round_popup_menus(sub)
    for menu in menus:
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        menu.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

"""About Forge: the brand mark, version, links, credits and system info."""

from __future__ import annotations

import platform
import sys
from importlib import resources
from importlib.util import find_spec

from PyQt6.QtCore import PYQT_VERSION_STR, QByteArray, QRectF, Qt, QUrl, qVersion
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from forge import APP_NAME, ISSUES_URL, MANUAL_URL, REPOSITORY_URL, __version__
from forge.core import paths
from forge.i18n.translator import tr
from forge.themes import tokens
from forge.themes.theme import Theme
from forge.ui.framed_dialog import FramedDialog
from forge.ui.result_dialog import copy_to_clipboard

MARK_SIZE = 88
WIDTH = 600


def _qscintilla_version() -> str:
    try:
        from PyQt6.Qsci import QSCINTILLA_VERSION_STR

        return str(QSCINTILLA_VERSION_STR)
    except ImportError:  # pragma: no cover - always installed
        return "?"


def system_info() -> str:
    """Plain text for bug reports: versions, platform and Forge's folders."""
    web = tr("installed") if find_spec("PyQt6.QtWebEngineWidgets") else tr("not installed")
    rows = [
        f"{APP_NAME} {__version__}",
        f"Python {platform.python_version()} ({sys.platform})",
        f"Qt {qVersion()}, PyQt {PYQT_VERSION_STR}, QScintilla {_qscintilla_version()}",
        f"Qt WebEngine (web extra): {web}",
        f"{platform.platform()}",
        f"Settings: {paths.config_dir()}",
        f"Logs: {paths.log_dir()}",
    ]
    return "\n".join(rows)


def _mark_pixmap(size: int) -> QPixmap:
    data = resources.files("forge.resources.icons").joinpath("forge-mark.svg").read_bytes()
    renderer = QSvgRenderer(QByteArray(data))
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if isinstance(app, QGuiApplication) else 1.0
    scale = max(2.0, ratio)
    view = renderer.viewBoxF()
    height = round(size * scale)
    width = round(height * view.width() / view.height())
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, width, height))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def _link(text: str, url: str, parent: QWidget) -> QPushButton:
    button = QPushButton(text, parent)
    button.setObjectName("aboutLink")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setAutoDefault(False)
    button.setToolTip(url)
    button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return button


class AboutDialog(FramedDialog):
    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(tr("About Forge"), parent)
        self.setObjectName("aboutDialog")
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._hero())
        layout.addWidget(self._details(theme), 1)
        # Wrapped text needs the width to know its height.
        outer = self.layout()
        height = outer.totalHeightForWidth(WIDTH) if outer is not None else -1
        if height > 0:
            self.setFixedSize(WIDTH, height)
        else:
            self.setFixedWidth(WIDTH)

    # The brand band: always dark, as in the brand guide.
    def _hero(self) -> QWidget:
        hero = QFrame(self.body)
        hero.setObjectName("aboutHero")
        top = tokens.mix(tokens.NIGHT_BLUE, tokens.SKY_BLUE, 0.16)
        hero.setStyleSheet(
            "QFrame#aboutHero { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {top}, stop:1 {tokens.NIGHT_BLUE}); }}"
            f"QLabel {{ background: transparent; color: {tokens.LIGHT}; }}"
        )
        row = QHBoxLayout(hero)
        row.setContentsMargins(32, 28, 32, 26)
        row.setSpacing(24)
        mark = QLabel(hero)
        mark.setObjectName("aboutMark")
        mark.setPixmap(_mark_pixmap(MARK_SIZE))
        row.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(6)
        wordmark = QLabel(APP_NAME.upper(), hero)
        font = QFont("Inter")
        font.setPixelSize(40)
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 9)
        wordmark.setFont(font)
        tagline = QLabel(tr("Your tools. Your workflow."), hero)
        tagline.setStyleSheet(f"color: {tokens.SKY_BLUE}; font-size: 17px;")
        pillars = QLabel(tr("CROSS-PLATFORM · OPEN SOURCE · BUILT FOR DEVELOPERS"), hero)
        small = QFont("Inter")
        small.setPixelSize(10)
        small.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.1)
        pillars.setFont(small)
        pillars.setStyleSheet(f"color: {tokens.mix(tokens.LIGHT, tokens.NIGHT_BLUE, 0.35)};")
        text.addWidget(wordmark)
        text.addWidget(tagline)
        text.addSpacing(6)
        text.addWidget(pillars)
        row.addLayout(text, 1)
        return hero

    def _details(self, theme: Theme) -> QWidget:
        details = QWidget(self.body)
        layout = QVBoxLayout(details)
        layout.setContentsMargins(32, 20, 32, 18)
        layout.setSpacing(10)

        version = QLabel(tr("Version {version}", version=__version__), details)
        version.setObjectName("aboutVersion")
        description = QLabel(
            tr(
                "A fast, lightweight text editor for macOS, Linux and Windows, built "
                "around developer tooling for JSON, CSV, Markdown, XML and YAML."
            ),
            details,
        )
        description.setWordWrap(True)
        layout.addWidget(version)
        layout.addWidget(description)

        links = QHBoxLayout()
        links.setSpacing(8)
        links.addWidget(_link(tr("Manual"), MANUAL_URL, details))
        links.addWidget(_link(tr("Source Code"), REPOSITORY_URL, details))
        links.addWidget(_link(tr("Report a Problem"), ISSUES_URL, details))
        links.addStretch(1)
        layout.addSpacing(4)
        layout.addLayout(links)

        built = QLabel(
            tr(
                "Built with Python {python}, Qt {qt} and QScintilla {qsci}. Includes Inter and "
                "JetBrains Mono (SIL Open Font License), Lucide icons (ISC) and Mermaid (MIT).",
                python=platform.python_version(),
                qt=qVersion(),
                qsci=_qscintilla_version(),
            ),
            details,
        )
        built.setObjectName("aboutCredits")
        built.setWordWrap(True)
        license_text = QLabel(
            tr("Free software under the GNU General Public License, version 3."), details
        )
        license_text.setObjectName("aboutCredits")
        license_text.setWordWrap(True)
        layout.addSpacing(6)
        layout.addWidget(built)
        layout.addWidget(license_text)

        line = QFrame(details)
        line.setObjectName("aboutRule")
        line.setFixedHeight(1)
        layout.addSpacing(6)
        layout.addWidget(line)

        footer = QHBoxLayout()
        family = QLabel(tr("Forge is part of Bytefulminds."), details)
        family.setObjectName("aboutCredits")
        buttons = QDialogButtonBox(details)
        self.copy_button = buttons.addButton(
            tr("Copy System Info"), QDialogButtonBox.ButtonRole.ActionRole
        )
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        assert self.copy_button is not None and close is not None
        self.copy_button.setAutoDefault(False)
        close.setDefault(True)
        self.copy_button.clicked.connect(self._copy_info)
        buttons.rejected.connect(self.reject)
        footer.addWidget(family, 1)
        footer.addWidget(buttons)
        layout.addLayout(footer)
        return details

    def _copy_info(self) -> None:
        copy_to_clipboard(system_info())
        if self.copy_button is not None:
            self.copy_button.setText(tr("Copied"))

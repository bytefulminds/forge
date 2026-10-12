"""Application entry point."""

from __future__ import annotations

import logging
import sys
from importlib import resources
from pathlib import Path

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QFileOpenEvent, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication

from forge import APP_ID, APP_NAME, __version__
from forge.core.log import setup_logging
from forge.core.settings import Settings
from forge.i18n.translator import install_language, resolve_language

log = logging.getLogger(__name__)


class ForgeApplication(QApplication):
    """QApplication that forwards macOS 'open with' requests to the main window."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.window: object | None = None
        self._pending: list[Path] = []

    def event(self, e: QEvent | None) -> bool:
        if isinstance(e, QFileOpenEvent) and e.file():
            path = Path(e.file())
            from forge.ui.main_window import MainWindow

            if isinstance(self.window, MainWindow):
                self.window.open_path(path)
            else:
                self._pending.append(path)
            return True
        return super().event(e)

    def take_pending(self) -> list[Path]:
        pending, self._pending = self._pending, []
        return pending


def _app_icon() -> QIcon:
    data = resources.files("forge.resources.icons").joinpath("forge.svg").read_bytes()
    pixmap = QPixmap()
    pixmap.loadFromData(data, "SVG")
    return QIcon(pixmap)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    setup_logging()
    log.info("Starting %s %s", APP_NAME, __version__)

    app = ForgeApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationDomain("bytefulminds.nl")
    app.setDesktopFileName(APP_ID)
    app.setStyle("Fusion")
    app.setWindowIcon(_app_icon())

    settings = Settings.load()
    install_language(resolve_language(settings.appearance.language))

    # Imported after the language is installed so menus are built translated.
    from forge.ui.main_window import MainWindow

    window = MainWindow(settings)
    app.window = window
    window.open_paths(Path(arg) for arg in argv[1:] if not arg.startswith("-"))
    window.open_paths(app.take_pending())
    window.show()
    return app.exec()

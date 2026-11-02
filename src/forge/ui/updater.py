"""Updates in the window: check GitLab, offer a new version, download it,
check it against its SHA-256 and install it (see forge.core.installer).

Network traffic goes through Qt (QNetworkAccessManager), which uses the
operating system's certificates, also in the packaged builds.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from forge import APP_NAME, REPOSITORY_URL, __version__
from forge.core import installer, updates
from forge.core.tasks import run_in_background
from forge.i18n.translator import tr
from forge.ui import message_box
from forge.ui.framed_dialog import FramedDialog
from forge.ui.notice_bar import Notice, NoticeBar

if TYPE_CHECKING:
    from forge.ui.main_window import MainWindow

log = logging.getLogger(__name__)

AUTOMATIC_DELAY_MS = 8_000  # let Forge start in peace first
RELEASES_PAGE = f"{REPOSITORY_URL}/-/releases"


def _request(url: str, timeout_ms: int) -> QNetworkRequest:
    request = QNetworkRequest(QUrl(url))
    request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, f"Forge/{__version__}")
    request.setRawHeader(b"Accept", b"application/json, */*")
    request.setTransferTimeout(timeout_ms)  # without data for this long: give up
    return request


def _failure(reply: QNetworkReply) -> str | None:
    if reply.error() == QNetworkReply.NetworkError.NoError:
        return None
    return reply.errorString() or tr("network error")


class Updater(QObject):
    """Owned by the main window; ``bar`` is its notice in the window."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.window = window
        self.network = QNetworkAccessManager(self)
        self.bar = NoticeBar(window)
        self.kind = updates.installation_kind()
        self.release: updates.Release | None = None
        self._checking = False

    # Checking --------------------------------------------------------------------------

    def schedule_automatic_check(self) -> None:
        settings = self.window.settings.updates
        if not (settings.check_automatically and updates.automatic_checks_allowed()):
            return
        if updates.check_due(settings.last_check):
            QTimer.singleShot(AUTOMATIC_DELAY_MS, lambda: self.check(manual=False))

    def check(self, manual: bool) -> None:
        """Ask GitLab for the latest release. ``manual`` (Help > Check for Updates)
        always answers; an automatic check only speaks up for a new version."""
        if self._checking:
            return
        self._checking = True
        reply = self.network.get(_request(updates.releases_url(), 20_000))
        assert reply is not None
        reply.finished.connect(lambda: self._checked(reply, manual))

    def _checked(self, reply: QNetworkReply, manual: bool) -> None:
        self._checking = False
        reply.deleteLater()
        settings = self.window.settings
        settings.updates.last_check = datetime.now(UTC).isoformat(timespec="seconds")
        settings.save()
        error = _failure(reply)
        try:
            if error is not None:
                raise updates.UpdateError(error)
            release = updates.parse_release(json.loads(bytes(reply.readAll().data())))
        except (updates.UpdateError, ValueError) as exc:
            log.info("Update check failed: %s", exc)
            if manual:
                message_box.warning(
                    self.window,
                    tr("Check for Updates"),
                    tr("Forge could not check for updates: {error}", error=str(exc)),
                )
            return
        if not updates.is_newer(release.version, __version__):
            if manual:
                message_box.information(
                    self.window,
                    tr("Check for Updates"),
                    tr("You have the latest version of Forge ({version}).", version=__version__),
                )
            return
        self.release = release
        if manual:
            self.show_dialog()
        elif release.version != settings.updates.skipped_version:
            self.show_notice()

    # Offering -------------------------------------------------------------------------

    def can_install(self) -> bool:
        return self.release is not None and self.release.download_for(self.kind) is not None

    def show_notice(self) -> None:
        if self.release is None:
            return
        primary = (
            (tr("Install and Restart"), lambda: self.show_dialog(install=True))
            if self.can_install()
            else (tr("Download"), self.open_release_page)
        )
        notice = Notice(
            "info",
            tr("Forge {version} is available.", version=self.release.version),
            [primary, (tr("What's New"), self.show_dialog)],
        )
        self.bar.show_notice(notice, self.hide_notice)

    def hide_notice(self) -> None:
        self.bar.show_notice(None, lambda: None)

    def show_dialog(self, install: bool = False) -> None:
        if self.release is None:
            return
        self.hide_notice()
        dialog = UpdateDialog(self, self.release)
        if install:
            QTimer.singleShot(0, dialog.install)
        dialog.exec()

    def skip(self, version: str) -> None:
        self.window.settings.updates.skipped_version = version
        self.window.settings.save()
        self.hide_notice()

    def open_release_page(self) -> None:
        page = self.release.page_url if self.release and self.release.page_url else RELEASES_PAGE
        QDesktopServices.openUrl(QUrl(page))

    # Restarting -----------------------------------------------------------------------

    def restart_with(self, start: Callable[[], None]) -> bool:
        """Close the window (the session keeps all text), run ``start``, quit.
        False when the window did not close (the user kept it open)."""
        self.window.close()
        if self.window.isVisible():
            return False
        start()
        app = QApplication.instance()
        if app is not None:
            app.quit()
        return True


class UpdateDialog(FramedDialog):
    """What's new, and the download and installation with their progress."""

    def __init__(self, updater: Updater, release: updates.Release) -> None:
        super().__init__(tr("Update Forge"), updater.window)
        self.updater = updater
        self.release = release
        self.folder: Path | None = None
        self._reply: QNetworkReply | None = None

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 18, 24, 16)
        layout.setSpacing(10)
        heading = QLabel(
            tr("{name} {version} is available", name=APP_NAME, version=release.version), self
        )
        heading.setObjectName("aboutVersion")
        current = QLabel(tr("You have version {version}.", version=__version__), self)
        current.setObjectName("resultNote")
        self.notes = QTextBrowser(self)
        self.notes.setObjectName("updateNotes")
        self.notes.setOpenExternalLinks(True)
        self.notes.setMarkdown(release.notes or tr("No release notes."))
        self.notes.setMinimumHeight(260)
        self.progress = QProgressBar(self)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.status = QLabel(self)
        self.status.setObjectName("resultNote")
        self.status.setWordWrap(True)
        self.status.hide()
        if not updater.can_install():
            self._say(self._why_manual())

        buttons = QHBoxLayout()
        self.skip_button = QPushButton(tr("Skip This Version"), self)
        self.later_button = QPushButton(tr("Later"), self)
        self.install_button = QPushButton(
            tr("Install and Restart") if updater.can_install() else tr("Open Release Page"), self
        )
        self.install_button.setProperty("primary", "true")
        self.install_button.setDefault(True)
        buttons.addWidget(self.skip_button)
        buttons.addStretch(1)
        buttons.addWidget(self.later_button)
        buttons.addWidget(self.install_button)
        self.skip_button.clicked.connect(self._skip)
        self.later_button.clicked.connect(self.reject)
        self.install_button.clicked.connect(
            self.install if updater.can_install() else self._open_page
        )

        for widget in (heading, current, self.notes, self.progress, self.status):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        self.setMinimumWidth(560)
        self.resize(620, 520)

    # States ----------------------------------------------------------------------------

    def _why_manual(self) -> str:
        if self.updater.kind is None:
            return tr("This copy of Forge runs from source; update it with git pull.")
        return tr("This release has no download for your system yet.")

    def _say(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setObjectName("cronError" if error else "resultNote")
        style = self.status.style()
        if style is not None:
            style.unpolish(self.status)
            style.polish(self.status)
        self.status.show()

    def _busy(self, busy: bool) -> None:
        self.install_button.setEnabled(not busy)
        self.skip_button.setEnabled(not busy)
        self.later_button.setText(tr("Cancel") if busy else tr("Later"))
        self.progress.setVisible(busy)

    def _fail(self, error: str) -> None:
        self._busy(False)
        self.install_button.setText(tr("Try Again"))
        self._say(tr("The update did not work: {error}", error=error), error=True)
        self._cleanup()

    def _skip(self) -> None:
        self.updater.skip(self.release.version)
        self.accept()

    def _open_page(self) -> None:
        self.updater.open_release_page()
        self.accept()

    def reject(self) -> None:
        if self._reply is not None:
            self._reply.abort()
        self._cleanup()
        super().reject()

    def _cleanup(self) -> None:
        if self.folder is not None:
            shutil.rmtree(self.folder, ignore_errors=True)
            self.folder = None

    # Download ------------------------------------------------------------------------

    def install(self) -> None:
        url = self.release.download_for(self.updater.kind)
        if url is None:
            return
        self._busy(True)
        self.progress.setRange(0, 0)
        self._say(tr("Checking the download..."))
        self.folder = Path(tempfile.mkdtemp(prefix="forge-update-"))
        reply = self.updater.network.get(_request(updates.checksum_url(url), 30_000))
        assert reply is not None
        self._reply = reply
        reply.finished.connect(lambda: self._got_checksum(reply, url))

    def _got_checksum(self, reply: QNetworkReply, url: str) -> None:
        self._reply = None
        reply.deleteLater()
        if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
            return
        try:
            error = _failure(reply)
            if error is not None:
                raise updates.UpdateError(error)
            expected = updates.parse_checksum(
                bytes(reply.readAll().data()).decode("ascii", "replace")
            )
        except updates.UpdateError as exc:
            self._fail(tr("its checksum is not available ({error})", error=str(exc)))
            return
        assert self.folder is not None
        target = self.folder / QUrl(url).fileName()
        handle = target.open("wb")
        self._say(tr("Downloading {name}...", name=target.name))
        download = self.updater.network.get(_request(url, 60_000))
        assert download is not None
        self._reply = download

        def write() -> None:
            handle.write(bytes(download.readAll().data()))

        def progress(received: int, total: int) -> None:
            if total > 0:
                self.progress.setRange(0, total)
                self.progress.setValue(received)

        download.readyRead.connect(write)
        download.downloadProgress.connect(progress)
        download.finished.connect(lambda: self._downloaded(download, handle, target, expected))

    def _downloaded(
        self, reply: QNetworkReply, handle: BinaryIO, target: Path, expected: str
    ) -> None:
        self._reply = None
        reply.deleteLater()
        if reply.error() == QNetworkReply.NetworkError.OperationCanceledError:
            handle.close()
            return
        handle.write(bytes(reply.readAll().data()))
        handle.close()
        error = _failure(reply)
        if error is not None:
            self._fail(error)
            return
        self.progress.setRange(0, 0)
        self._say(tr("Checking the download..."))
        run_in_background(
            lambda: updates.verify(target, expected),
            lambda _result: self._verified(target),
            lambda exc: self._fail(str(exc)),
        )

    # Installation --------------------------------------------------------------------

    def _verified(self, package: Path) -> None:
        self._say(tr("Installing..."))
        kind = self.updater.kind
        if kind == updates.WINDOWS_INSTALLER:
            command = installer.windows_setup_command(package)
            self.folder = None  # the installer runs from there after Forge quits
            self._restart(lambda: installer.launch_detached(command))
        elif kind == updates.APPIMAGE:
            appimage = Path(os.environ["APPIMAGE"])
            run_in_background(
                lambda: installer.replace_appimage(package, appimage),
                lambda _r: self._restart(
                    lambda: installer.launch_detached([str(appimage)]), installed=True
                ),
                lambda exc: self._fail(str(exc)),
            )
        elif kind == updates.MACOS_APP:
            app = updates.macos_app_bundle()
            if app is None:
                self._fail(tr("Forge.app was not found"))
                return
            run_in_background(
                lambda: installer.stage_macos_app(package, app),
                lambda staged: self._swap_macos(app, staged),
                lambda exc: self._fail(str(exc)),
            )

    def _swap_macos(self, app: Path, staged: Path) -> None:
        script = installer.write_swap_script(app, staged, os.getpid())
        self._restart(lambda: installer.launch_detached([str(script)]))

    def _restart(self, start: Callable[[], None], installed: bool = False) -> None:
        """Quit and start the new version. ``installed``: the files are already
        replaced, so a refused quit only postpones the new version."""
        folder = self.folder
        self.folder = None
        self.accept()
        if not self.updater.restart_with(start):
            text = (
                tr(
                    "Forge {version} starts the next time you open Forge.",
                    version=self.release.version,
                )
                if installed
                else tr("The update was stopped because Forge stayed open.")
            )
            message_box.information(self.updater.window, tr("Update Forge"), text)
            if folder is not None:
                shutil.rmtree(folder, ignore_errors=True)
            return
        if folder is not None and sys.platform != "win32":
            shutil.rmtree(folder, ignore_errors=True)

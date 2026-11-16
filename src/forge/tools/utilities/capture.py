"""Taking screenshots on each platform.

* Windows and X11: Qt grabs the screen directly.
* macOS: the same for the full screen, but only after the user allowed Forge
  (or, when run from source, the terminal or IDE that started it) under Privacy &
  Security > Screen Recording; without it macOS hands back the wallpaper. An area
  is chosen with macOS's own crosshair (``screencapture -i``, as Cmd+Shift+4).
* Wayland: programs may not read the screen, so we ask the desktop through
  the xdg-desktop-portal Screenshot interface. The desktop shows its own
  picker and gives us the picture as a file.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote, urlparse

from PyQt6.QtCore import QObject, QProcess, pyqtSlot
from PyQt6.QtGui import QCursor, QGuiApplication, QPixmap, QScreen


def is_wayland() -> bool:
    return QGuiApplication.platformName().startswith("wayland")


def screen_under_cursor() -> QScreen | None:
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


def grab(screen: QScreen) -> QPixmap:
    """The whole screen, at its physical resolution."""
    return screen.grabWindow()


# macOS screen recording permission -----------------------------------------------


def _core_graphics() -> ctypes.CDLL | None:
    if sys.platform != "darwin":
        return None
    path = ctypes.util.find_library("CoreGraphics")
    if not path:
        return None
    try:
        return ctypes.CDLL(path)
    except OSError:
        return None


def mac_capture_allowed(ask: bool = True) -> bool:
    """True when macOS lets Forge record the screen (always True elsewhere).

    With ``ask`` the first refusal shows macOS's own permission prompt.
    """
    library = _core_graphics()
    if library is None:
        return True
    try:
        preflight = library.CGPreflightScreenCaptureAccess
        preflight.restype = ctypes.c_bool
        if preflight():
            return True
        if ask:
            request = library.CGRequestScreenCaptureAccess
            request.restype = ctypes.c_bool
            return bool(request())
    except AttributeError:  # macOS older than 10.15: no permission needed
        return True
    return False


def bring_app_to_front() -> None:
    """macOS: make Forge the active app, so its next window opens on top.

    Started from the global shortcut, Forge is in the background; without this
    its windows may open behind the app you were working in, or the annotation
    window behind Forge's own main window.
    """
    if sys.platform != "darwin":
        return
    path = ctypes.util.find_library("objc")
    if not path:
        return
    try:
        objc = ctypes.cdll.LoadLibrary(path)
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send = objc.objc_msgSend
        send.restype = ctypes.c_void_p
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        app = send(
            objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication")
        )
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        send(app, objc.sel_registerName(b"activateIgnoringOtherApps:"), True)
    except (OSError, AttributeError):
        pass


# macOS: the system's own area picker -------------------------------------------------


class MacAreaCapture(QObject):
    """Run ``screencapture -i``; ``done(pixmap or None, error)`` follows. Esc in
    the crosshair cancels (no file, no error); Space switches to a window."""

    def __init__(
        self, done: Callable[[QPixmap | None, str], None], ratio: float, parent: QObject
    ) -> None:
        super().__init__(parent)
        self._done: Callable[[QPixmap | None, str], None] | None = done
        self._ratio = ratio
        self._folder = tempfile.TemporaryDirectory(prefix="forge-snip-")
        self._file = Path(self._folder.name) / "area.png"
        self._process = QProcess(self)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(lambda _error: self._finished())

    def start(self) -> None:
        # -i interactive area (Space: window), -x no sound, -o no window shadow.
        self._process.start("/usr/sbin/screencapture", ["-i", "-x", "-o", str(self._file)])

    def _finished(self, *_args: object) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        pixmap: QPixmap | None = None
        error = ""
        if self._file.exists():
            pixmap = QPixmap(str(self._file))
            if pixmap.isNull():
                pixmap, error = None, "could not read the screenshot"
            else:
                pixmap.setDevicePixelRatio(self._ratio)
        elif self._process.error() == QProcess.ProcessError.FailedToStart:
            error = "screencapture is not available"
        self._folder.cleanup()  # our own temporary folder
        done, self._done = self._done, None
        if done is not None:
            done(pixmap, error)
        self.deleteLater()


# Wayland: xdg-desktop-portal ------------------------------------------------------

PORTAL = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SCREENSHOT = "org.freedesktop.portal.Screenshot"
REQUEST = "org.freedesktop.portal.Request"


class PortalScreenshot(QObject):
    """Ask the desktop for a screenshot; ``done(pixmap or None, error)`` follows."""

    def __init__(self, done: Callable[[QPixmap | None, str], None], parent: QObject) -> None:
        super().__init__(parent)
        self._done = done
        self._finished = False

    def start(self, interactive: bool) -> None:
        from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            self._finish(None, "no D-Bus session")
            return
        token = f"forge{os.getpid()}"
        sender = bus.baseService().lstrip(":").replace(".", "_")
        handle = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        bus.connect(PORTAL, handle, REQUEST, "Response", self._response)
        portal = QDBusInterface(PORTAL, PORTAL_PATH, SCREENSHOT, bus)
        options = {"handle_token": token, "interactive": interactive, "modal": True}
        reply = portal.call("Screenshot", "", options)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            self._finish(None, reply.errorMessage() or reply.errorName())

    @pyqtSlot("uint", "QVariantMap")
    def _response(self, code: int, results: dict[str, object]) -> None:
        if code != 0:
            self._finish(None, "")  # cancelled by the user
            return
        uri = str(results.get("uri", ""))
        path = Path(unquote(urlparse(uri).path))
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._finish(None, f"could not read {path}")
            return
        self._finish(pixmap, "")  # the desktop's own file stays where it saved it

    def _finish(self, pixmap: QPixmap | None, error: str) -> None:
        if self._finished:
            return
        self._finished = True
        self._done(pixmap, error)
        self.deleteLater()

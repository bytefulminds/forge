"""System-wide keyboard shortcuts: they work while Forge is in the background
or minimized. Each platform has its own way, all reached with ctypes:

* Windows: ``RegisterHotKey``; the key arrives as WM_HOTKEY in Qt's event loop.
* macOS: Carbon ``RegisterEventHotKey`` (still how macOS apps do this).
* Linux X11: ``XGrabKey`` on the root window, on a connection of our own.
* Wayland lets no program grab keys. There Forge offers ``forge --snip`` to bind
  in the desktop's own keyboard settings instead.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import sys
from collections.abc import Callable

from PyQt6 import sip
from PyQt6.QtCore import (
    QAbstractNativeEventFilter,
    QByteArray,
    QCoreApplication,
    QKeyCombination,
    QObject,
    QSocketNotifier,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QGuiApplication, QKeySequence

log = logging.getLogger(__name__)


class HotkeyError(Exception):
    """The shortcut could not be registered; the message says why."""


def is_wayland() -> bool:
    return QGuiApplication.platformName().startswith("wayland")


def supported() -> bool:
    """Whether this system lets Forge register a global shortcut (not on
    Wayland, and not without a real screen, as in tests)."""
    return QGuiApplication.platformName() in ("windows", "cocoa", "xcb")


def parse(sequence: str) -> tuple[Qt.Key, Qt.KeyboardModifier]:
    """The key and modifiers of the first combination in ``sequence``."""
    keys = QKeySequence(sequence)
    if keys.isEmpty():
        raise HotkeyError("no key combination")
    combination: QKeyCombination = keys[0]
    return combination.key(), combination.keyboardModifiers()


def _later(callback: Callable[[], None]) -> None:
    """Run ``callback`` from Qt's event loop, not inside a native callback."""
    QTimer.singleShot(0, callback)


# Windows ----------------------------------------------------------------------------

_WM_HOTKEY = 0x0312
_MOD_ALT, _MOD_CONTROL, _MOD_SHIFT, _MOD_WIN, _MOD_NOREPEAT = 1, 2, 4, 8, 0x4000


def windows_key(key: Qt.Key) -> int:
    value = int(key.value)
    if 0x30 <= value <= 0x39 or 0x41 <= value <= 0x5A:  # 0-9, A-Z: the same codes
        return value
    if Qt.Key.Key_F1.value <= value <= Qt.Key.Key_F24.value:
        return 0x70 + value - Qt.Key.Key_F1.value
    raise HotkeyError("use a letter, a digit or F1 to F24")


def windows_modifiers(mods: Qt.KeyboardModifier) -> int:
    value = _MOD_NOREPEAT
    if mods & Qt.KeyboardModifier.ControlModifier:
        value |= _MOD_CONTROL
    if mods & Qt.KeyboardModifier.AltModifier:
        value |= _MOD_ALT
    if mods & Qt.KeyboardModifier.ShiftModifier:
        value |= _MOD_SHIFT
    if mods & Qt.KeyboardModifier.MetaModifier:
        value |= _MOD_WIN
    return value


class _WindowsFilter(QAbstractNativeEventFilter):
    def __init__(self, ident: int, fire: Callable[[], None]) -> None:
        super().__init__()
        self.ident = ident
        self.fire = fire

    def nativeEventFilter(  # type: ignore[override]
        self, event_type: QByteArray | bytes | bytearray | memoryview | None, message: object
    ) -> tuple[bool, int]:
        if isinstance(event_type, QByteArray):
            kind = event_type.data()
        else:
            kind = bytes(event_type) if event_type is not None else b""
        if kind == b"windows_generic_MSG" and message is not None:
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(int(message))  # type: ignore[call-overload]
            if msg.message == _WM_HOTKEY and msg.wParam == self.ident:
                _later(self.fire)
                return True, 0
        return False, 0


class _WindowsHotkey:
    IDENT = 0xF0E1

    def __init__(self, key: Qt.Key, mods: Qt.KeyboardModifier, fire: Callable[[], None]) -> None:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        if not user32.RegisterHotKey(None, self.IDENT, windows_modifiers(mods), windows_key(key)):
            raise HotkeyError("taken")
        self._user32 = user32
        self._filter = _WindowsFilter(self.IDENT, fire)
        app = QCoreApplication.instance()
        assert app is not None
        app.installNativeEventFilter(self._filter)

    def close(self) -> None:
        self._user32.UnregisterHotKey(None, self.IDENT)
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self._filter)


# macOS --------------------------------------------------------------------------------

# Virtual key codes of the ANSI keyboard layout (Carbon's kVK_* constants).
MAC_KEYS = {
    "A": 0x00, "S": 0x01, "D": 0x02, "F": 0x03, "H": 0x04, "G": 0x05, "Z": 0x06, "X": 0x07,
    "C": 0x08, "V": 0x09, "B": 0x0B, "Q": 0x0C, "W": 0x0D, "E": 0x0E, "R": 0x0F, "Y": 0x10,
    "T": 0x11, "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17, "9": 0x19,
    "7": 0x1A, "8": 0x1C, "0": 0x1D, "O": 0x1F, "U": 0x20, "I": 0x22, "P": 0x23, "L": 0x25,
    "J": 0x26, "K": 0x28, "N": 0x2D, "M": 0x2E,
}  # fmt: skip
MAC_FUNCTION_KEYS = (0x7A, 0x78, 0x63, 0x76, 0x60, 0x61, 0x62, 0x64, 0x65, 0x6D, 0x67, 0x6F)
_CMD, _SHIFT, _OPTION, _CONTROL = 0x100, 0x200, 0x800, 0x1000


def mac_key(key: Qt.Key) -> int:
    value = int(key.value)
    if 0x30 <= value <= 0x39 or 0x41 <= value <= 0x5A:
        return MAC_KEYS[chr(value)]
    index = value - Qt.Key.Key_F1.value
    if 0 <= index < len(MAC_FUNCTION_KEYS):
        return MAC_FUNCTION_KEYS[index]
    raise HotkeyError("use a letter, a digit or F1 to F12")


def mac_modifiers(mods: Qt.KeyboardModifier) -> int:
    """Qt's Ctrl is the Command key on macOS and Meta is Control."""
    value = 0
    if mods & Qt.KeyboardModifier.ControlModifier:
        value |= _CMD
    if mods & Qt.KeyboardModifier.ShiftModifier:
        value |= _SHIFT
    if mods & Qt.KeyboardModifier.AltModifier:
        value |= _OPTION
    if mods & Qt.KeyboardModifier.MetaModifier:
        value |= _CONTROL
    return value


def _fourcc(text: str) -> int:
    return int.from_bytes(text.encode("ascii"), "big")


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


class _MacHotkey:
    def __init__(self, key: Qt.Key, mods: Qt.KeyboardModifier, fire: Callable[[], None]) -> None:
        carbon = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
        carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
        carbon.InstallEventHandler.argtypes = [
            ctypes.c_void_p, _HANDLER, ctypes.c_uint32, ctypes.POINTER(_EventTypeSpec),
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ]  # fmt: skip
        carbon.RegisterEventHotKey.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
        ]  # fmt: skip
        carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
        self._carbon = carbon

        def handler(_call: object, _event: object, _data: object) -> int:
            _later(fire)
            return 0  # noErr

        self._callback = _HANDLER(handler)  # keep a reference while registered
        target = carbon.GetApplicationEventTarget()
        spec = _EventTypeSpec(_fourcc("keyb"), 5)  # kEventHotKeyPressed
        self._handler = ctypes.c_void_p()
        status = carbon.InstallEventHandler(
            target, self._callback, 1, ctypes.byref(spec), None, ctypes.byref(self._handler)
        )
        if status != 0:
            raise HotkeyError(f"InstallEventHandler failed ({status})")
        self._hotkey = ctypes.c_void_p()
        status = carbon.RegisterEventHotKey(
            mac_key(key), mac_modifiers(mods), _EventHotKeyID(_fourcc("Frge"), 1), target, 0,
            ctypes.byref(self._hotkey),
        )  # fmt: skip
        if status != 0:
            carbon.RemoveEventHandler(self._handler)
            raise HotkeyError(
                "taken" if status == -9878 else f"RegisterEventHotKey failed ({status})"
            )

    def close(self) -> None:
        self._carbon.UnregisterEventHotKey(self._hotkey)
        self._carbon.RemoveEventHandler(self._handler)


# Linux X11 ----------------------------------------------------------------------------

_SHIFT_MASK, _LOCK_MASK, _CONTROL_MASK, _MOD1_MASK, _MOD2_MASK, _MOD4_MASK = 1, 2, 4, 8, 16, 64
_KEY_PRESS = 2
_GRAB_MODE_ASYNC = 1


def x11_keysym_name(key: Qt.Key) -> str:
    value = int(key.value)
    if 0x30 <= value <= 0x39:
        return chr(value)
    if 0x41 <= value <= 0x5A:
        return chr(value).lower()
    if Qt.Key.Key_F1.value <= value <= Qt.Key.Key_F24.value:
        return f"F{value - Qt.Key.Key_F1.value + 1}"
    raise HotkeyError("use a letter, a digit or F1 to F24")


def x11_modifiers(mods: Qt.KeyboardModifier) -> int:
    value = 0
    if mods & Qt.KeyboardModifier.ShiftModifier:
        value |= _SHIFT_MASK
    if mods & Qt.KeyboardModifier.ControlModifier:
        value |= _CONTROL_MASK
    if mods & Qt.KeyboardModifier.AltModifier:
        value |= _MOD1_MASK
    if mods & Qt.KeyboardModifier.MetaModifier:
        value |= _MOD4_MASK
    return value


class _XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int), ("display", ctypes.c_void_p), ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong), ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte), ("minor_code", ctypes.c_ubyte),
    ]  # fmt: skip


_X_ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(_XErrorEvent))


class _X11Hotkey:
    """A passive grab on the root window, on our own X connection."""

    def __init__(self, key: Qt.Key, mods: Qt.KeyboardModifier, fire: Callable[[], None]) -> None:
        path = ctypes.util.find_library("X11")
        if not path:
            raise HotkeyError("libX11 is not installed")
        x = ctypes.cdll.LoadLibrary(path)
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        for name in ("XDefaultRootWindow",):
            getattr(x, name).restype = ctypes.c_ulong
            getattr(x, name).argtypes = [ctypes.c_void_p]
        x.XStringToKeysym.restype = ctypes.c_ulong
        x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        x.XKeysymToKeycode.restype = ctypes.c_ubyte
        x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x.XGrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong,
                               ctypes.c_int, ctypes.c_int, ctypes.c_int]  # fmt: skip
        x.XUngrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong]
        x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x.XPending.argtypes = [ctypes.c_void_p]
        x.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        x.XConnectionNumber.argtypes = [ctypes.c_void_p]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x.XSetErrorHandler.restype = ctypes.c_void_p
        x.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        display = x.XOpenDisplay(None)
        if not display:
            raise HotkeyError("no X display")
        self._x, self._display = x, display
        self._root = x.XDefaultRootWindow(display)
        keycode = x.XKeysymToKeycode(display, x.XStringToKeysym(x11_keysym_name(key).encode()))
        if not keycode:
            x.XCloseDisplay(display)
            raise HotkeyError("this key is not on the keyboard")
        self._keycode = int(keycode)
        base = x11_modifiers(mods)
        # The same key with Caps Lock and Num Lock on, so those do not get in the way.
        self._masks = [
            base | extra for extra in (0, _LOCK_MASK, _MOD2_MASK, _LOCK_MASK | _MOD2_MASK)
        ]
        failed: list[int] = []

        def on_error(_display: object, _event: object) -> int:
            failed.append(1)  # BadAccess: another program holds this combination
            return 0

        handler = _X_ERROR_HANDLER(on_error)
        previous = x.XSetErrorHandler(ctypes.cast(handler, ctypes.c_void_p))
        for mask in self._masks:
            x.XGrabKey(display, self._keycode, mask, self._root, 0, _GRAB_MODE_ASYNC,
                       _GRAB_MODE_ASYNC)  # fmt: skip
        x.XSync(display, 0)
        x.XSetErrorHandler(previous)
        if failed:
            self._ungrab()
            x.XCloseDisplay(display)
            raise HotkeyError("taken")
        self._fire = fire
        self._event = ctypes.create_string_buffer(256)  # an XEvent union
        self._notifier = QSocketNotifier(x.XConnectionNumber(display), QSocketNotifier.Type.Read)
        self._notifier.activated.connect(self._read)

    def _read(self, *_args: object) -> None:
        x = self._x
        pressed = False
        while x.XPending(self._display):
            x.XNextEvent(self._display, self._event)
            kind = ctypes.c_int.from_buffer(self._event).value
            pressed = pressed or kind == _KEY_PRESS
        if pressed:
            _later(self._fire)

    def _ungrab(self) -> None:
        for mask in self._masks:
            self._x.XUngrabKey(self._display, self._keycode, mask, self._root)
        self._x.XSync(self._display, 0)

    def close(self) -> None:
        if not sip.isdeleted(self._notifier):
            self._notifier.setEnabled(False)
            self._notifier.deleteLater()
        self._ungrab()
        self._x.XCloseDisplay(self._display)


# The public face -----------------------------------------------------------------------


class GlobalHotkey(QObject):
    """One system-wide shortcut; ``callback`` runs in Qt's event loop."""

    def __init__(self, sequence: str, callback: Callable[[], None], parent: QObject) -> None:
        super().__init__(parent)
        if not supported():
            raise HotkeyError("not supported here")
        key, mods = parse(sequence)
        if not mods & ~Qt.KeyboardModifier.KeypadModifier:
            raise HotkeyError("add Ctrl, Alt or Shift")
        backend: type[_WindowsHotkey] | type[_MacHotkey] | type[_X11Hotkey]
        if sys.platform == "win32":
            backend = _WindowsHotkey
        elif sys.platform == "darwin":
            backend = _MacHotkey
        else:
            backend = _X11Hotkey
        self._backend: _WindowsHotkey | _MacHotkey | _X11Hotkey | None = backend(
            key, mods, callback
        )
        self.sequence = sequence
        log.info("Global shortcut %s registered", sequence)

    def close(self) -> None:
        if self._backend is not None:
            try:
                self._backend.close()
            except (OSError, AttributeError):
                log.warning("Could not release the global shortcut", exc_info=True)
            self._backend = None

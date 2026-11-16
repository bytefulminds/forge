"""Global shortcut: key mapping per platform, the X11 grab (on a private Xvfb),
and the channel that ``forge --snip`` uses to reach a running Forge."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import time
from collections.abc import Iterator

import pytest
from PyQt6.QtCore import QObject, Qt
from pytestqt.qtbot import QtBot

from forge.ui import global_hotkey as gh
from forge.ui import instance

K = Qt.KeyboardModifier


def test_parse_and_platform_codes() -> None:
    key, mods = gh.parse("Ctrl+Alt+Shift+S")
    assert key == Qt.Key.Key_S
    assert mods == K.ControlModifier | K.AltModifier | K.ShiftModifier
    assert gh.windows_key(Qt.Key.Key_S) == 0x53 and gh.windows_key(Qt.Key.Key_F5) == 0x74
    assert gh.windows_modifiers(mods) == 0x4000 | 2 | 1 | 4
    assert gh.mac_key(Qt.Key.Key_S) == 0x01 and gh.mac_key(Qt.Key.Key_F1) == 0x7A
    assert gh.mac_modifiers(mods) == 0x100 | 0x800 | 0x200  # Ctrl is Command on macOS
    assert gh.mac_modifiers(K.MetaModifier) == 0x1000
    assert gh.x11_keysym_name(Qt.Key.Key_S) == "s" and gh.x11_keysym_name(Qt.Key.Key_F12) == "F12"
    assert gh.x11_modifiers(mods) == 4 | 8 | 1
    with pytest.raises(gh.HotkeyError):
        gh.windows_key(Qt.Key.Key_Space)
    with pytest.raises(gh.HotkeyError):
        gh.parse("")


def test_unsupported_without_a_real_screen(qtbot: QtBot) -> None:
    from forge.core.settings import Settings
    from forge.ui.main_window import MainWindow

    window = MainWindow(Settings())
    qtbot.addWidget(window)
    api = window.extension_host.api("forge.utilities")
    assert not gh.supported()  # tests run offscreen
    assert api.set_global_shortcut("snip", "Ctrl+Alt+Shift+S", lambda: None) == "unsupported"
    assert api.set_global_shortcut("snip", None, lambda: None) == ""


@pytest.fixture
def xvfb(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    if not shutil.which("Xvfb") or not ctypes.util.find_library("Xtst"):
        pytest.skip("needs Xvfb and libXtst")
    display = ":87"
    process = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "640x480x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.6)
    monkeypatch.setenv("DISPLAY", display)
    try:
        yield display
    finally:
        process.terminate()
        process.wait(5)


def _press(display: str, keysym: str, modifiers: list[str]) -> None:
    """Type a key combination with XTest, as a person would."""
    x = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "")
    xtst = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Xtst") or "")
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XStringToKeysym.restype = ctypes.c_ulong
    x.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x.XKeysymToKeycode.restype = ctypes.c_ubyte
    x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    x.XFlush.argtypes = [ctypes.c_void_p]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    dpy = x.XOpenDisplay(display.encode())
    codes = [x.XKeysymToKeycode(dpy, x.XStringToKeysym(n.encode())) for n in [*modifiers, keysym]]
    for code in codes:
        xtst.XTestFakeKeyEvent(dpy, code, 1, 0)
    for code in reversed(codes):
        xtst.XTestFakeKeyEvent(dpy, code, 0, 0)
    x.XFlush(dpy)
    x.XCloseDisplay(dpy)


def test_x11_grab_fires_and_reports_a_taken_key(qtbot: QtBot, xvfb: str) -> None:
    fired: list[int] = []
    first = gh._X11Hotkey(Qt.Key.Key_S, K.ControlModifier | K.AltModifier, lambda: fired.append(1))
    try:
        _press(xvfb, "s", ["Control_L", "Alt_L"])
        qtbot.waitUntil(lambda: bool(fired), timeout=3000)
        with pytest.raises(gh.HotkeyError, match="taken"):
            gh._X11Hotkey(Qt.Key.Key_S, K.ControlModifier | K.AltModifier, lambda: None)
    finally:
        first.close()
    again = gh._X11Hotkey(Qt.Key.Key_S, K.ControlModifier | K.AltModifier, lambda: None)
    again.close()  # free again after close


def test_forge_snip_reaches_the_running_forge(qtbot: QtBot) -> None:
    name = f"forge-test-{os.getpid()}"
    received: list[str] = []
    owner = QObject()
    server = instance.InstanceServer(received.append, owner, name)
    assert server.listening
    second = instance.InstanceServer(received.append, owner, name)
    assert not second.listening  # the first Forge keeps it
    assert instance.send("snip", name)
    qtbot.waitUntil(lambda: received == ["snip"], timeout=3000)
    server.close()
    assert not instance.send("snip", name)

"""Where the window buttons go, following the operating system (no Qt).

- macOS: close, minimize and zoom as traffic lights on the left.
- Windows: minimize, maximize and close on the right.
- Linux: the desktop's own setting. GNOME and most GTK desktops keep it in
  ``org.gnome.desktop.wm.preferences button-layout`` (``"appmenu:close"`` on
  stock GNOME, ``"close,minimize,maximize:"`` with buttons on the left), KDE
  in ``kwinrc`` (``ButtonsOnLeft``/``ButtonsOnRight``, letters such as ``IAX``).
  Without a readable setting: minimize, maximize and close on the right.
"""

from __future__ import annotations

import configparser
import contextlib
import functools
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

CLOSE, MINIMIZE, MAXIMIZE = "close", "minimize", "maximize"
_KNOWN = (CLOSE, MINIMIZE, MAXIMIZE)
_KDE_LETTERS = {"X": CLOSE, "I": MINIMIZE, "A": MAXIMIZE}


@dataclass(frozen=True)
class ButtonLayout:
    left: tuple[str, ...]
    right: tuple[str, ...]
    mac: bool = False  # traffic lights instead of flat buttons


DEFAULT = ButtonLayout((), (MINIMIZE, MAXIMIZE, CLOSE))
MAC = ButtonLayout((CLOSE, MINIMIZE, MAXIMIZE), (), mac=True)


def parse_gnome(value: str) -> ButtonLayout | None:
    """``"close,minimize:appmenu"`` style; unknown names (appmenu, icon) are skipped."""
    text = value.strip().strip("'\"")
    if ":" not in text:
        return None
    left, _, right = text.partition(":")

    def names(part: str) -> tuple[str, ...]:
        return tuple(n.strip() for n in part.split(",") if n.strip() in _KNOWN)

    layout = ButtonLayout(names(left), names(right))
    return layout if layout.left or layout.right else None


def parse_kde(left: str, right: str) -> ButtonLayout:
    def names(letters: str) -> tuple[str, ...]:
        return tuple(_KDE_LETTERS[c] for c in letters if c in _KDE_LETTERS)

    return ButtonLayout(names(left), names(right))


def _kde_layout(home: Path) -> ButtonLayout:
    config = configparser.ConfigParser(interpolation=None, strict=False)
    with contextlib.suppress(OSError, configparser.Error):
        config.read(home / ".config" / "kwinrc", encoding="utf-8")
    section = "org.kde.kdecoration2"
    left = config.get(section, "ButtonsOnLeft", fallback="MS")
    right = config.get(section, "ButtonsOnRight", fallback="HIAX")
    return parse_kde(left, right)


def _gsettings() -> str | None:
    tool = shutil.which("gsettings")
    if tool is None:
        return None
    from forge.core.installer import clean_environment

    try:
        done = subprocess.run(
            [tool, "get", "org.gnome.desktop.wm.preferences", "button-layout"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
            env=clean_environment(),  # not the libraries bundled with Forge
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _gtk_settings(home: Path) -> str | None:
    for version in ("gtk-4.0", "gtk-3.0"):
        config = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            config.read(home / ".config" / version / "settings.ini", encoding="utf-8")
        except (OSError, configparser.Error):
            continue
        value = config.get("Settings", "gtk-decoration-layout", fallback=None)
        if value:
            return value
    return None


def detect(
    platform: str = sys.platform,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
    gsettings: Callable[[], str | None] = _gsettings,
) -> ButtonLayout:
    if platform == "darwin":
        return MAC
    if not platform.startswith("linux"):
        return DEFAULT
    environ = dict(os.environ) if environ is None else environ
    home = home or Path.home()
    desktop = environ.get("XDG_CURRENT_DESKTOP", "").upper()
    if "KDE" in desktop:
        return _kde_layout(home)
    for value in (gsettings(), _gtk_settings(home)):
        layout = parse_gnome(value) if value else None
        if layout is not None:
            return layout
    return DEFAULT


@functools.cache
def current() -> ButtonLayout:
    """The layout for this session (read once)."""
    return detect()

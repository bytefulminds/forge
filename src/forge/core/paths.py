"""Platform specific locations for config, cache and log files.

Linux follows the XDG spec (``~/.config/forge``), macOS uses
``~/Library/Application Support/Forge``. ``FORGE_HOME`` overrides everything,
which tests use to stay out of the real user folders.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import platformdirs

# Linux uses lower case folder names (~/.config/forge); macOS and Windows "Forge".
_APP_DIR_NAME = "forge" if sys.platform.startswith("linux") else "Forge"


def _override() -> Path | None:
    value = os.environ.get("FORGE_HOME")
    return Path(value) if value else None


def config_dir() -> Path:
    base = _override()
    path = base / "config" if base else Path(platformdirs.user_config_dir(_APP_DIR_NAME, False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    base = _override()
    path = base / "cache" if base else Path(platformdirs.user_cache_dir(_APP_DIR_NAME, False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    base = _override()
    path = base / "logs" if base else Path(platformdirs.user_log_dir(_APP_DIR_NAME, False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return config_dir() / "settings.toml"

"""Typed user settings stored as TOML in the platform config directory."""

from __future__ import annotations

import logging
import sys
import tomllib
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import tomli_w

from forge.core import paths

log = logging.getLogger(__name__)

# Bundled with Forge (see forge/resources/fonts).
_DEFAULT_FONT = "JetBrains Mono"
_DEFAULT_FONT_SIZE = 13 if sys.platform == "darwin" else 10

# Bump when a default changes in a way that should replace values saved by
# older versions (see _migrate).
SCHEMA_VERSION = 2


@dataclass
class EditorSettings:
    font_family: str = _DEFAULT_FONT
    font_size: int = _DEFAULT_FONT_SIZE
    tab_width: int = 4
    use_spaces: bool = True
    word_wrap: bool = False
    show_whitespace: bool = False
    show_line_numbers: bool = True
    highlight_current_line: bool = True
    rainbow_brackets: bool = True
    rainbow_indentation: bool = True
    check_syntax: bool = True
    autocomplete: bool = True
    autocomplete_threshold: int = 3
    # The per-document toolbar with language tools and view buttons.
    show_toolbar: bool = True


@dataclass
class GeneralSettings:
    # Notepad++ "Remember current session": reopen tabs, including unsaved text.
    remember_session: bool = True
    # Native Open / Save dialogs (Finder, GTK, KDE) instead of Forge styled ones.
    native_file_dialogs: bool = False


@dataclass
class AppearanceSettings:
    # "dark", "blue", "light" or "system" (follow the operating system).
    theme: str = "dark"
    # Empty means "follow the system locale".
    language: str = ""


@dataclass
class UpdateSettings:
    # Look for a new release at startup, at most once a day.
    check_automatically: bool = True
    # When the last automatic check ran (ISO 8601, UTC).
    last_check: str = ""
    # A version the user chose to skip; it is not offered again.
    skipped_version: str = ""


@dataclass
class WindowSettings:
    # Base64 encoded QMainWindow.saveGeometry(); empty means "use the default size".
    geometry: str = ""


@dataclass
class Settings:
    general: GeneralSettings = field(default_factory=GeneralSettings)
    editor: EditorSettings = field(default_factory=EditorSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    window: WindowSettings = field(default_factory=WindowSettings)
    updates: UpdateSettings = field(default_factory=UpdateSettings)
    # Per built-in tool settings, keyed by extension id (see ForgeAPI.setting).
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    schema: int = SCHEMA_VERSION

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        path = path or paths.settings_file()
        if not path.exists():
            return cls()
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            log.exception("Could not read %s, using defaults", path)
            return cls()
        _migrate(raw)
        return cls(
            general=_build(GeneralSettings, raw.get("general", {})),
            editor=_build(EditorSettings, raw.get("editor", {})),
            appearance=_build(AppearanceSettings, raw.get("appearance", {})),
            window=_build(WindowSettings, raw.get("window", {})),
            updates=_build(UpdateSettings, raw.get("updates", {})),
            tools=_tools(raw.get("tools", {})),
        )

    def save(self, path: Path | None = None) -> None:
        path = path or paths.settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomli_w.dumps(asdict(self)), encoding="utf-8")


def _tools(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}


def _migrate(raw: dict[str, Any]) -> None:
    """Drop values written by older versions whose defaults have changed."""
    if raw.get("schema", 1) < 2:
        # v1 saved the platform monospace font; v2 bundles JetBrains Mono.
        editor = raw.get("editor")
        if isinstance(editor, dict):
            editor.pop("font_family", None)
            editor.pop("font_size", None)


def _build[T](cls: type[T], raw: Any) -> T:
    """Create ``cls`` from ``raw``, ignoring unknown keys and wrongly typed values."""
    instance = cls()
    if not isinstance(raw, dict):
        return instance
    for f in fields(cls):  # type: ignore[arg-type]
        if f.name not in raw:
            continue
        value = raw[f.name]
        default = getattr(instance, f.name)
        if type(value) is type(default):
            setattr(instance, f.name, value)
        else:
            log.warning(
                "Ignoring setting %s=%r (expected %s)", f.name, value, type(default).__name__
            )
    return instance

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

_DEFAULT_FONT = "Menlo" if sys.platform == "darwin" else "Monospace"


@dataclass
class EditorSettings:
    font_family: str = _DEFAULT_FONT
    font_size: int = 13
    tab_width: int = 4
    use_spaces: bool = True
    word_wrap: bool = False
    show_whitespace: bool = False
    show_line_numbers: bool = True


@dataclass
class AppearanceSettings:
    theme: str = "dark"
    # Empty means "follow the system locale".
    language: str = ""


@dataclass
class Settings:
    editor: EditorSettings = field(default_factory=EditorSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)

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
        return cls(
            editor=_build(EditorSettings, raw.get("editor", {})),
            appearance=_build(AppearanceSettings, raw.get("appearance", {})),
        )

    def save(self, path: Path | None = None) -> None:
        path = path or paths.settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomli_w.dumps(asdict(self)), encoding="utf-8")


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

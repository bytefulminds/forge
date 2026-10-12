from __future__ import annotations

from pathlib import Path

from forge.core import paths
from forge.core.settings import Settings


def test_defaults_when_missing(forge_home: Path) -> None:
    settings = Settings.load()
    assert settings.appearance.theme == "dark"
    assert settings.editor.tab_width == 4


def test_round_trip(forge_home: Path) -> None:
    settings = Settings()
    settings.editor.tab_width = 2
    settings.appearance.language = "nl"
    settings.save()
    assert paths.settings_file().is_relative_to(forge_home)
    loaded = Settings.load()
    assert loaded.editor.tab_width == 2
    assert loaded.appearance.language == "nl"


def test_corrupt_or_wrong_types_fall_back(forge_home: Path) -> None:
    file = paths.settings_file()
    file.write_text('[editor]\ntab_width = "wide"\nunknown = 1\n[appearance]\ntheme = "light"\n')
    loaded = Settings.load()
    assert loaded.editor.tab_width == 4
    assert loaded.appearance.theme == "light"

    file.write_text("this is [not toml")
    assert Settings.load() == Settings()


def test_v1_font_settings_are_migrated(forge_home: Path) -> None:
    paths.settings_file().write_text(
        '[editor]\nfont_family = "Menlo"\nfont_size = 13\ntab_width = 2\n'
    )
    loaded = Settings.load()
    assert loaded.editor.font_family == "JetBrains Mono"
    assert loaded.editor.tab_width == 2

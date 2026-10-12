from __future__ import annotations

import string
from pathlib import Path

import pytest

from forge.i18n.catalog import LANGUAGES, SOURCE_LANGUAGE, find_translatable_strings, load_catalog

SRC = Path(__file__).resolve().parents[1] / "src" / "forge"
TRANSLATED = [code for code in LANGUAGES if code != SOURCE_LANGUAGE]


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.mark.parametrize("language", TRANSLATED)
def test_catalog_is_complete(language: str) -> None:
    catalog = load_catalog(language)
    missing = sorted(find_translatable_strings(SRC) - catalog.keys())
    assert missing == [], f"Missing {language} translations: {missing}"


@pytest.mark.parametrize("language", TRANSLATED)
def test_catalog_has_no_stale_entries(language: str) -> None:
    stale = sorted(load_catalog(language).keys() - find_translatable_strings(SRC))
    assert stale == [], f"Unused {language} translations: {stale}"


@pytest.mark.parametrize("language", TRANSLATED)
def test_placeholders_match(language: str) -> None:
    for source, translated in load_catalog(language).items():
        assert _placeholders(source) == _placeholders(translated), source

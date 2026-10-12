"""Runtime translation: ``tr()`` for Forge strings, QTranslator for Qt strings."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

from forge.i18n.catalog import LANGUAGES, SOURCE_LANGUAGE, load_catalog

log = logging.getLogger(__name__)

_catalog: dict[str, str] = {}
_language = SOURCE_LANGUAGE
_qt_translator: QTranslator | None = None


def tr(text: str, /, **values: object) -> str:
    """Translate ``text`` and fill ``{placeholders}`` with ``values``."""
    translated = _catalog.get(text, text)
    return translated.format(**values) if values else translated


def current_language() -> str:
    return _language


def resolve_language(preferred: str) -> str:
    """Pick the configured language, else the system locale, else English."""
    if preferred in LANGUAGES:
        return preferred
    system = QLocale.system().name().split("_")[0]
    return system if system in LANGUAGES else SOURCE_LANGUAGE


def install_language(language: str) -> None:
    global _catalog, _language, _qt_translator
    _language = language
    _catalog = load_catalog(language)

    app = QCoreApplication.instance()
    if app is None:
        return
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if language == SOURCE_LANGUAGE:
        return
    translator = QTranslator(app)
    qt_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(f"qtbase_{language}", qt_dir):
        app.installTranslator(translator)
        _qt_translator = translator
    else:
        log.info("No Qt base translation for %s in %s", language, qt_dir)

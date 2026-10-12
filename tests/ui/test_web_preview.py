"""Rich Markdown preview. Needs the web extra and a browser engine, so it is
opt-in: FORGE_TEST_WEBENGINE=1 uv run pytest tests/ui/test_web_preview.py"""

from __future__ import annotations

import importlib.util
import os

import pytest
from pytestqt.qtbot import QtBot

from forge.themes.theme import get_theme

pytestmark = pytest.mark.skipif(
    not os.environ.get("FORGE_TEST_WEBENGINE")
    or importlib.util.find_spec("PyQt6.QtWebEngineWidgets") is None,
    reason="set FORGE_TEST_WEBENGINE=1 with the web extra installed",
)


def test_mermaid_diagram_is_drawn(qtbot: QtBot) -> None:
    from forge.ui.web_preview import WebMarkdownPreview

    preview = WebMarkdownPreview(get_theme("dark", True))
    qtbot.addWidget(preview)
    preview.show()
    preview.show_document("# Hi\n\n```mermaid\ngraph LR\n  A-->B\n```\n", None)
    page = preview.web.page()
    assert page is not None
    result: list[object] = []

    def probe() -> None:
        page.runJavaScript("document.querySelectorAll('svg').length", result.append)

    def drawn() -> None:
        probe()
        assert result and result[-1] == 1

    qtbot.waitUntil(drawn, timeout=20_000)

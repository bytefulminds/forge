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


def test_copy_button_and_scroll_signal(qtbot: QtBot) -> None:
    from PyQt6.QtGui import QGuiApplication

    from forge.ui.web_preview import WebMarkdownPreview

    preview = WebMarkdownPreview(get_theme("dark", True))
    qtbot.addWidget(preview)
    preview.resize(600, 300)
    preview.show()
    text = "```sh\necho hi\n```\n\n" + "\n\n".join(f"Line {n}" for n in range(300))
    preview.show_document(text, None)
    page = preview.web.page()
    assert page is not None
    found: list[object] = []
    qtbot.waitUntil(
        lambda: (
            page.runJavaScript("document.querySelectorAll('a.copy').length", found.append)
            or (bool(found) and found[-1] == 1)
        ),
        timeout=20_000,
    )
    page.runJavaScript("document.querySelector('a.copy').click()")
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    qtbot.waitUntil(lambda: clipboard.text() == "echo hi\n", timeout=5_000)

    ratios: list[float] = []
    preview.scrolled.connect(ratios.append)
    page.runJavaScript("window.scrollTo(0, 400)")
    qtbot.waitUntil(lambda: bool(ratios) and ratios[-1] > 0, timeout=5_000)

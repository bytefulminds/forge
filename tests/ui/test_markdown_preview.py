"""Basic Markdown preview: copy buttons and scrolling linked both ways."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.ui.main_window import MainWindow
from forge.ui.previews import MarkdownPreview

LONG = "# Notes\n\n```python\nprint('hi')\n```\n\n" + "\n\n".join(
    f"Paragraph {n}" for n in range(200)
)


def test_copy_button_copies_the_code(qtbot: QtBot) -> None:
    from forge.themes.theme import get_theme

    preview = MarkdownPreview(get_theme("dark"))
    qtbot.addWidget(preview)
    preview.show_document(LONG, None)
    preview.browser.anchorClicked.emit(QUrl("forge-copy:0"))
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None and clipboard.text() == "print('hi')\n"


def test_scrolling_is_linked_both_ways(qtbot: QtBot, tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text(LONG, encoding="utf-8")
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    window.resize(1000, 600)
    window.show()
    tab = window.open_path(path)
    assert tab is not None
    window.set_view_mode(tab, "split")
    page = window.page_of(tab)
    preview = page.preview
    assert isinstance(preview, MarkdownPreview)
    qtbot.waitUntil(lambda: (preview.browser.verticalScrollBar().maximum() or 0) > 0)
    editor_bar = tab.verticalScrollBar()
    preview_bar = preview.browser.verticalScrollBar()
    assert editor_bar is not None and preview_bar is not None

    # The preview leads: the editor follows.
    preview_bar.setValue(preview_bar.maximum() // 2)
    assert editor_bar.value() > 0
    page._release_scroll()

    # The editor leads: the preview follows.
    editor_bar.setValue(0)
    assert preview_bar.value() == 0

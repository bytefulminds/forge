"""Markdown extras: footnotes, table of contents, tables, images, diagram editor."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.tools.markdown_tool import edits
from forge.ui.main_window import MainWindow


def make_markdown(qtbot: QtBot, text: str) -> tuple[MainWindow, object]:
    from forge.editor.lexers import language_by_id

    window = MainWindow(Settings())
    qtbot.addWidget(window)
    tab = window.current_tab()
    assert tab is not None
    window.set_document_language(language_by_id("markdown"))
    tab.setText(text)
    return window, tab


def test_toc_skips_code_and_front_matter() -> None:
    text = "---\ntitle: x\n---\n# Doc\n## A\n```\n## not\n```\n### B\n"
    assert edits.headings(text) == [(1, "Doc"), (2, "A"), (3, "B")]
    toc = edits.table_of_contents(text)
    assert toc.splitlines() == [edits.TOC_START, "- [A](#a)", "  - [B](#b)", edits.TOC_END]
    assert edits.replace_toc("x\n" + edits.TOC_START + "\nold\n" + edits.TOC_END, "NEW") == "x\nNEW"


def test_footnote_and_toc_commands(qtbot: QtBot) -> None:
    window, tab = make_markdown(qtbot, "# T\n\n## One\n\nText")
    tab.setCursorPosition(4, 4)  # type: ignore[attr-defined]
    window.extension_host.run_command("markdown.footnote")
    assert tab.text() == "# T\n\n## One\n\nText[^1]\n\n[^1]: "  # type: ignore[attr-defined]
    tab.setCursorPosition(1, 0)  # type: ignore[attr-defined]
    window.extension_host.run_command("markdown.toc")
    assert "- [One](#one)" in tab.text()  # type: ignore[attr-defined]
    tab.insert("## Two\n")  # type: ignore[attr-defined]
    window.extension_host.run_command("markdown.toc")
    text = tab.text()  # type: ignore[attr-defined]
    assert text.count(edits.TOC_START) == 1 and "- [Two](#two)" in text


def test_line_up_table_at_cursor(qtbot: QtBot) -> None:
    window, tab = make_markdown(qtbot, "intro\n|a|bb|\n|-|-|\n|ccc|d|\nend")
    tab.setCursorPosition(2, 1)  # type: ignore[attr-defined]
    window.extension_host.run_command("markdown.format_table")
    assert tab.text().splitlines()[1:4] == [  # type: ignore[attr-defined]
        "| a   | bb  |",
        "| --- | --- |",
        "| ccc | d   |",
    ]


def test_image_is_relative_to_the_document(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.extensions.api import ForgeAPI

    doc = tmp_path / "notes.md"
    doc.write_text("x\n")
    (tmp_path / "img").mkdir()
    picture = tmp_path / "img" / "my chart.png"
    picture.write_bytes(b"png")
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    tab = window.open_path(doc)
    assert tab is not None
    monkeypatch.setattr(ForgeAPI, "choose_files", lambda _self, _title: [picture])
    window.extension_host.run_command("markdown.image")
    assert "![my chart](img/my%20chart.png)" in tab.text()


def test_diagram_editor_builds_and_replaces_the_block(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.tools.markdown_tool import diagram

    window, tab = make_markdown(
        qtbot, "# Flow\n\n```mermaid\nflowchart TD\n  A[Start] --> B[End]\n```\n"
    )
    tab.setCursorPosition(4, 2)  # type: ignore[attr-defined]

    def draw(self: diagram.DiagramDialog) -> int:
        scene = self.scene
        assert set(scene.nodes) == {"A", "B"}
        new = scene.add_node("diamond", QPointF(0, 300))
        self.label.setText("Check?")
        self._label_edited("Check?")
        scene.connect_nodes(scene.nodes["B"], new)
        scene.nodes["A"].setSelected(True)
        new.setSelected(False)
        scene.clearSelection()
        scene.nodes["A"].setSelected(True)
        scene.delete_selected()
        return int(self.DialogCode.Accepted.value)

    monkeypatch.setattr(diagram.DiagramDialog, "exec", draw)
    window.extension_host.run_command("markdown.diagram")
    text = tab.text()  # type: ignore[attr-defined]
    assert text.count("```mermaid") == 1
    assert "C{Check?}" in text and "B --> C" in text and "A[Start]" not in text
    assert "%% forge-layout:" in text


def test_diagram_editor_refuses_other_diagrams(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.extensions.api import ForgeAPI

    window, tab = make_markdown(qtbot, "```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n")
    tab.setCursorPosition(1, 0)  # type: ignore[attr-defined]
    told: list[str] = []
    monkeypatch.setattr(ForgeAPI, "inform", lambda _s, _t, text: told.append(text))
    window.extension_host.run_command("markdown.diagram")
    assert told and "flowcharts" in told[0]

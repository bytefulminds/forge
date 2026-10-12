from __future__ import annotations

import ast
import re
from dataclasses import fields
from pathlib import Path

import pytest

from forge.themes.theme import THEMES, Theme
from forge.themes.tokens import contrast_ratio

SRC = Path(__file__).resolve().parents[2] / "src" / "forge"
HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
AA = 4.5

ALL_THEMES = pytest.mark.parametrize("theme", THEMES.values(), ids=lambda t: t.id)


@ALL_THEMES
def test_text_contrast_meets_wcag_aa(theme: Theme) -> None:
    for bg in (theme.editor_bg, theme.chrome_bg, theme.elevated_bg, theme.hover_bg):
        assert contrast_ratio(theme.text, bg) >= AA
        assert contrast_ratio(theme.text_muted, bg) >= AA, f"text_muted on {bg}"
    assert contrast_ratio(theme.text, theme.menu_selected_bg) >= AA
    assert contrast_ratio(theme.text, theme.selection) >= AA


@ALL_THEMES
def test_margin_and_accent_contrast(theme: Theme) -> None:
    for bg in (theme.margin_bg, theme.caret_line):
        assert contrast_ratio(theme.margin_text, bg) >= AA
    assert contrast_ratio(theme.on_accent, theme.accent) >= AA
    for color in (theme.accent, theme.error, theme.warning, theme.success):
        assert contrast_ratio(color, theme.editor_bg) >= AA, color
        assert contrast_ratio(color, theme.chrome_bg) >= AA, color
    # Non-text UI component (focus ring): WCAG 1.4.11 asks for 3:1.
    assert contrast_ratio(theme.focus, theme.editor_bg) >= 3


@ALL_THEMES
def test_syntax_colors_are_readable(theme: Theme) -> None:
    for f in fields(theme.syntax):
        color = getattr(theme.syntax, f.name)
        for bg in (theme.editor_bg, theme.caret_line):
            assert contrast_ratio(color, bg) >= AA, f"{theme.id}.{f.name} {color} on {bg}"


def test_no_hex_colors_outside_themes() -> None:
    offenders = []
    for file in SRC.rglob("*.py"):
        if file.parent.name == "themes":
            continue
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            is_text = isinstance(node, ast.Constant) and isinstance(node.value, str)
            if is_text and HEX.search(node.value):
                offenders.append(f"{file.relative_to(SRC)}:{node.lineno}")
    assert offenders == []


@ALL_THEMES
def test_rainbow_colors_are_readable(theme: Theme) -> None:
    assert len(theme.rainbow) >= 3
    for color in theme.rainbow:
        assert contrast_ratio(color, theme.editor_bg) >= AA, f"{theme.id} {color}"

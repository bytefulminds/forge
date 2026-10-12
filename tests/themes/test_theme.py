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


@pytest.mark.parametrize("theme", THEMES.values(), ids=lambda t: t.id)
def test_text_contrast_meets_wcag_aa(theme: Theme) -> None:
    assert contrast_ratio(theme.text, theme.background) >= 4.5
    assert contrast_ratio(theme.text, theme.surface) >= 4.5


@pytest.mark.parametrize("theme", THEMES.values(), ids=lambda t: t.id)
def test_syntax_colors_are_readable(theme: Theme) -> None:
    for f in fields(theme.syntax):
        color = getattr(theme.syntax, f.name)
        assert contrast_ratio(color, theme.background) >= 4.5, f"{theme.id}.{f.name} {color}"


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

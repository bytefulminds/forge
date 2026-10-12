"""Themes derived from the design tokens.

Every color the UI or the editor uses comes from a ``Theme``. No other module
may contain hex values.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.themes import tokens as t


@dataclass(frozen=True)
class SyntaxColors:
    default: str
    comment: str
    keyword: str
    string: str
    number: str
    operator: str
    tag: str
    attribute: str
    preprocessor: str
    error: str


@dataclass(frozen=True)
class Theme:
    id: str
    is_dark: bool
    background: str  # editor and window background
    surface: str  # panels, tab bar, menus
    surface_alt: str  # hover, inactive tabs
    border: str
    text: str
    text_muted: str
    accent: str  # interactive elements
    focus: str  # focus rings, active tab marker
    selection: str
    caret_line: str
    caret: str
    margin_background: str
    margin_text: str
    error: str
    warning: str
    success: str
    syntax: SyntaxColors


DARK = Theme(
    id="dark",
    is_dark=True,
    background=t.NIGHT_BLUE,
    surface=t.SLATE,
    surface_alt=t.mix(t.SLATE, t.LIGHT, 0.08),
    border=t.mix(t.SLATE, t.LIGHT, 0.15),
    text=t.LIGHT,
    text_muted=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.35),
    accent=t.SKY_BLUE,
    focus=t.LIME,
    selection=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.35),
    caret_line=t.mix(t.NIGHT_BLUE, t.SLATE, 0.6),
    caret=t.LIME,
    margin_background=t.mix(t.NIGHT_BLUE, t.SLATE, 0.5),
    margin_text=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.45),
    error=t.ERROR,
    warning=t.WARNING,
    success=t.LIME,
    syntax=SyntaxColors(
        default=t.LIGHT,
        comment=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.4),
        keyword=t.SKY_BLUE,
        string=t.LIME,
        number=t.CYAN,
        operator=t.mix(t.LIGHT, t.SKY_BLUE, 0.4),
        tag=t.SKY_BLUE,
        attribute=t.CYAN,
        preprocessor=t.mix(t.CYAN, t.LIME, 0.5),
        error=t.ERROR,
    ),
)

LIGHT = Theme(
    id="light",
    is_dark=False,
    background=t.mix(t.LIGHT, "#FFFFFF", 0.6),
    surface=t.LIGHT,
    surface_alt=t.mix(t.LIGHT, t.SLATE, 0.08),
    border=t.mix(t.LIGHT, t.SLATE, 0.2),
    text=t.NIGHT_BLUE,
    text_muted=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.4),
    accent=t.mix(t.SKY_BLUE, t.NIGHT_BLUE, 0.45),
    focus=t.mix(t.SKY_BLUE, t.NIGHT_BLUE, 0.2),
    selection=t.mix(t.LIGHT, t.SKY_BLUE, 0.35),
    caret_line=t.LIGHT,
    caret=t.NIGHT_BLUE,
    margin_background=t.LIGHT,
    margin_text=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.45),
    error=t.mix(t.ERROR, t.NIGHT_BLUE, 0.45),
    warning=t.mix(t.WARNING, t.NIGHT_BLUE, 0.6),
    success=t.mix(t.LIME, t.NIGHT_BLUE, 0.65),
    syntax=SyntaxColors(
        default=t.NIGHT_BLUE,
        comment=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.35),
        keyword=t.mix(t.SKY_BLUE, t.NIGHT_BLUE, 0.5),
        string=t.mix(t.LIME, t.NIGHT_BLUE, 0.65),
        number=t.mix(t.CYAN, t.NIGHT_BLUE, 0.6),
        operator=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.3),
        tag=t.mix(t.SKY_BLUE, t.NIGHT_BLUE, 0.5),
        attribute=t.mix(t.CYAN, t.NIGHT_BLUE, 0.6),
        preprocessor=t.mix(t.CYAN, t.NIGHT_BLUE, 0.55),
        error=t.mix(t.ERROR, t.NIGHT_BLUE, 0.45),
    ),
)

THEMES: dict[str, Theme] = {DARK.id: DARK, LIGHT.id: LIGHT}


def get_theme(theme_id: str) -> Theme:
    return THEMES.get(theme_id, DARK)

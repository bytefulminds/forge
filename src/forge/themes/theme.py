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
    editor_bg: str  # editor, active tab, gutter
    chrome_bg: str  # menu bar, tab bar, status bar
    elevated_bg: str  # menus, dialogs, tooltips
    hover_bg: str
    pressed_bg: str
    menu_selected_bg: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_disabled: str
    accent: str  # primary buttons, links, dirty marker
    accent_hover: str
    on_accent: str  # text on accent backgrounds
    focus: str  # focus rings, active tab marker
    selection: str
    caret: str
    caret_line: str
    margin_bg: str
    margin_text: str
    indent_guide: str
    brace_match_bg: str
    scroll_handle: str
    scroll_handle_hover: str
    error: str
    warning: str
    success: str
    syntax: SyntaxColors


_DARK_PREPROCESSOR = t.mix(t.CYAN, t.LIME, 0.5)

DARK = Theme(
    id="dark",
    is_dark=True,
    editor_bg=t.NIGHT_BLUE,
    chrome_bg=t.mix(t.NIGHT_BLUE, t.BLACK, 0.30),
    elevated_bg=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.08),
    hover_bg=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.12),
    pressed_bg=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.20),
    menu_selected_bg=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.22),
    border=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.18),
    border_strong=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.32),
    text=t.LIGHT,
    text_muted=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.32),
    text_disabled=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.62),
    accent=t.SKY_BLUE,
    accent_hover=t.mix(t.SKY_BLUE, t.LIGHT, 0.20),
    on_accent=t.NIGHT_BLUE,
    focus=t.SKY_BLUE,
    selection=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.30),
    caret=t.LIME,
    caret_line=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.06),
    margin_bg=t.NIGHT_BLUE,
    margin_text=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.44),
    indent_guide=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.12),
    brace_match_bg=t.mix(t.NIGHT_BLUE, t.CYAN, 0.28),
    scroll_handle=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.18),
    scroll_handle_hover=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.32),
    error=t.ERROR,
    warning=t.WARNING,
    success=t.LIME,
    syntax=SyntaxColors(
        default=t.LIGHT,
        comment=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.40),
        keyword=t.SKY_BLUE,
        string=t.LIME,
        number=t.CYAN,
        operator=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.18),
        tag=t.SKY_BLUE,
        attribute=t.mix(t.SKY_BLUE, t.LIGHT, 0.45),
        preprocessor=_DARK_PREPROCESSOR,
        error=t.ERROR,
    ),
)

LIGHT = Theme(
    id="light",
    is_dark=False,
    editor_bg=t.mix(t.LIGHT, t.WHITE, 0.80),
    chrome_bg=t.mix(t.LIGHT, t.WHITE, 0.45),
    elevated_bg=t.WHITE,
    hover_bg=t.LIGHT,
    pressed_bg=t.mix(t.LIGHT, t.SKY_BLUE, 0.22),
    menu_selected_bg=t.mix(t.WHITE, t.SKY_BLUE, 0.18),
    border=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.14),
    border_strong=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.28),
    text=t.NIGHT_BLUE,
    text_muted=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.38),
    text_disabled=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.62),
    accent=t.shade(t.SKY_BLUE, 0.42),
    accent_hover=t.shade(t.SKY_BLUE, 0.36),
    on_accent=t.WHITE,
    focus=t.shade(t.SKY_BLUE, 0.50),
    selection=t.mix(t.WHITE, t.SKY_BLUE, 0.26),
    caret=t.shade(t.SKY_BLUE, 0.42),
    caret_line=t.mix(t.WHITE, t.SKY_BLUE, 0.07),
    margin_bg=t.mix(t.LIGHT, t.WHITE, 0.80),
    margin_text=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.38),
    indent_guide=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.10),
    brace_match_bg=t.mix(t.WHITE, t.CYAN, 0.25),
    scroll_handle=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.18),
    scroll_handle_hover=t.mix(t.LIGHT, t.NIGHT_BLUE, 0.32),
    error=t.shade(t.ERROR, 0.42),
    warning=t.shade(t.WARNING, 0.30),
    success=t.shade(t.LIME, 0.22),
    syntax=SyntaxColors(
        default=t.NIGHT_BLUE,
        comment=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.38),
        keyword=t.shade(t.SKY_BLUE, 0.38),
        string=t.shade(t.LIME, 0.23),
        number=t.shade(t.CYAN, 0.27),
        operator=t.mix(t.NIGHT_BLUE, t.LIGHT, 0.25),
        tag=t.shade(t.SKY_BLUE, 0.38),
        attribute=t.mix(t.NIGHT_BLUE, t.SKY_BLUE, 0.45),
        preprocessor=t.shade(_DARK_PREPROCESSOR, 0.26),
        error=t.shade(t.ERROR, 0.42),
    ),
)

THEMES: dict[str, Theme] = {DARK.id: DARK, LIGHT.id: LIGHT}

# Settings value meaning "use dark or light like the operating system".
SYSTEM_THEME_ID = "system"
THEME_CHOICES: tuple[str, ...] = (DARK.id, LIGHT.id, SYSTEM_THEME_ID)


def get_theme(theme_id: str, system_is_dark: bool = True) -> Theme:
    if theme_id == SYSTEM_THEME_ID:
        return DARK if system_is_dark else LIGHT
    return THEMES.get(theme_id, DARK)

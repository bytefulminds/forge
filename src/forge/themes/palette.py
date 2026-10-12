"""QPalette built from a theme.

Without it Fusion falls back to its grey default palette, which shows up as
grey frame lines and white separators around themed widgets.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette

from forge.themes.theme import Theme

_Role = QPalette.ColorRole
_Group = QPalette.ColorGroup


def build_palette(theme: Theme) -> QPalette:
    palette = QPalette()
    roles: dict[QPalette.ColorRole, str] = {
        _Role.Window: theme.chrome_bg,
        _Role.WindowText: theme.text,
        _Role.Base: theme.editor_bg,
        _Role.AlternateBase: theme.elevated_bg,
        _Role.ToolTipBase: theme.elevated_bg,
        _Role.ToolTipText: theme.text,
        _Role.PlaceholderText: theme.text_muted,
        _Role.Text: theme.text,
        _Role.Button: theme.elevated_bg,
        _Role.ButtonText: theme.text,
        _Role.BrightText: theme.text,
        _Role.Highlight: theme.accent,
        _Role.HighlightedText: theme.on_accent,
        _Role.Link: theme.accent,
        _Role.LinkVisited: theme.accent,
        _Role.Light: theme.border,
        _Role.Midlight: theme.border,
        _Role.Mid: theme.border_strong,
        _Role.Dark: theme.border_strong,
        _Role.Shadow: theme.chrome_bg,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (_Role.Text, _Role.WindowText, _Role.ButtonText):
        palette.setColor(_Group.Disabled, role, QColor(theme.text_disabled))
    return palette

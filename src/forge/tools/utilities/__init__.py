"""Utility windows in the Tools menu: regex tester, code shot, snipping tool."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

_ACTIONS = "forge.tools.utilities.actions"

EXTENSION = ExtensionInfo(
    id="forge.utilities",
    title=lambda: tr("Utilities"),
    placement="tools-flat",  # below Cron Expression, in the same group
    commands=(
        CommandSpec(
            "utilities.regex",
            lambda: tr("Rege&x Tester..."),
            f"{_ACTIONS}:regex_tester",
            "Ctrl+Alt+R",
            icon="regex",
        ),
        CommandSpec(
            "utilities.codeshot",
            lambda: tr("&Code Shot..."),
            f"{_ACTIONS}:code_shot",
            "Ctrl+Alt+Shift+C",
            icon="camera",
            context="selection",
            tooltip=lambda: tr("The selected code as a tidy image to paste or save"),
        ),
        CommandSpec(
            "utilities.snip",
            lambda: tr("&Snipping Tool..."),
            f"{_ACTIONS}:snipping_tool",
            "Ctrl+Alt+Shift+S",
            icon="scissors",
        ),
    ),
    defaults={"snip_area": True, "snip_delay": 0, "snip_hide": True},
)

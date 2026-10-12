"""Compare two documents side by side (like the Notepad++ Compare plugin)."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

_ACTIONS = "forge.tools.compare.actions"

EXTENSION = ExtensionInfo(
    id="forge.compare",
    title=lambda: tr("Co&mpare"),
    commands=(
        CommandSpec(
            "compare.tab",
            lambda: tr("Compare with &Tab..."),
            f"{_ACTIONS}:compare_with_tab",
            "Ctrl+Alt+C",
        ),
        CommandSpec(
            "compare.saved",
            lambda: tr("Compare with &Saved Version"),
            f"{_ACTIONS}:compare_with_saved",
        ),
    ),
)

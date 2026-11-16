"""Compare two documents, a document and the clipboard, or two pasted texts."""

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
        CommandSpec(
            "compare.clipboard",
            lambda: tr("Compare with &Clipboard"),
            f"{_ACTIONS}:compare_with_clipboard",
        ),
        CommandSpec(
            "compare.quick",
            lambda: tr("&Quick Diff..."),
            f"{_ACTIONS}:quick_diff",
            "Ctrl+Alt+Shift+D",
            separator_before=True,
        ),
    ),
)

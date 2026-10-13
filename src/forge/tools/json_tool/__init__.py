"""JSON tools: format, minify, validate and a tree view (like JSTool / JSON Viewer)."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

_ACTIONS = "forge.tools.json_tool.actions"
_JSON = ("json",)

EXTENSION = ExtensionInfo(
    id="forge.json",
    title=lambda: tr("&JSON"),
    placement="language",
    commands=(
        CommandSpec(
            "json.format",
            lambda: tr("&Format JSON"),
            f"{_ACTIONS}:format_json",
            "Ctrl+Alt+Shift+M",
            languages=_JSON,
            icon="wand-sparkles",
        ),
        CommandSpec(
            "json.minify",
            lambda: tr("&Minify JSON"),
            f"{_ACTIONS}:minify_json",
            languages=_JSON,
            icon="minimize-2",
        ),
        CommandSpec(
            "json.validate",
            lambda: tr("&Validate JSON"),
            f"{_ACTIONS}:validate_json",
            languages=_JSON,
            icon="circle-check",
        ),
        CommandSpec(
            "json.tree",
            lambda: tr("Show JSON &Tree"),
            f"{_ACTIONS}:show_tree",
            separator_before=True,
            languages=_JSON,
            icon="list-tree",
        ),
    ),
)

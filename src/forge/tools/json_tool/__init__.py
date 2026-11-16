"""JSON tools: format, minify, validate, a tree view, path queries and conversions."""

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
        CommandSpec(
            "json.query",
            lambda: tr("&Path Query..."),
            f"{_ACTIONS}:path_query",
            "Ctrl+Alt+Shift+J",
            languages=_JSON,
            icon="text-search",
            tooltip=lambda: tr("Find values by path, like $.items[*].name"),
        ),
        CommandSpec(
            "json.sort_keys",
            lambda: tr("&Sort Keys"),
            f"{_ACTIONS}:sort_keys",
            separator_before=True,
            languages=_JSON,
            icon="arrow-down-a-z",
            tooltip=lambda: tr("Sort the keys of every object (A to Z)"),
        ),
        CommandSpec(
            "json.to_csv",
            lambda: tr("Convert to &CSV"),
            f"{_ACTIONS}:to_csv",
            languages=_JSON,
            icon="file-spreadsheet",
            tooltip=lambda: tr("Open an array of objects as CSV in a new tab"),
        ),
        CommandSpec(
            "json.to_yaml",
            lambda: tr("Convert to &YAML"),
            f"{_ACTIONS}:to_yaml",
            languages=_JSON,
            icon="file-code",
            tooltip=lambda: tr("Open the data as YAML in a new tab"),
        ),
    ),
)

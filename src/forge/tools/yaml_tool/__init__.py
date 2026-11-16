"""YAML tools: validation with error position and conversion to JSON."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

EXTENSION = ExtensionInfo(
    id="forge.yaml",
    title=lambda: tr("&YAML"),
    placement="language",
    commands=(
        CommandSpec(
            "yaml.validate",
            lambda: tr("&Validate YAML"),
            "forge.tools.yaml_tool.actions:validate_yaml",
            languages=("yaml",),
            icon="circle-check",
        ),
        CommandSpec(
            "yaml.to_json",
            lambda: tr("Convert to &JSON"),
            "forge.tools.yaml_tool.actions:to_json",
            languages=("yaml",),
            icon="braces",
            tooltip=lambda: tr("Open the data as JSON in a new tab"),
        ),
    ),
)

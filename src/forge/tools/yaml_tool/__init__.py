"""YAML tools: validation with error position (highlighting comes from the lexer)."""

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
    ),
)

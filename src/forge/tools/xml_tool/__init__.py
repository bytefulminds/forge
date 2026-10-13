"""XML Tools: pretty print, minify, well-formedness, XPath and tag auto-close."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

_ACTIONS = "forge.tools.xml_tool.actions"
_XML = ("xml",)

EXTENSION = ExtensionInfo(
    id="forge.xml",
    title=lambda: tr("&XML Tools"),
    placement="language",
    commands=(
        CommandSpec(
            "xml.pretty",
            lambda: tr("&Pretty Print"),
            f"{_ACTIONS}:pretty_print",
            "Ctrl+Alt+Shift+B",
            languages=_XML,
            icon="wand-sparkles",
        ),
        CommandSpec(
            "xml.minify",
            lambda: tr("&Minify"),
            f"{_ACTIONS}:minify",
            languages=_XML,
            icon="minimize-2",
        ),
        CommandSpec(
            "xml.check",
            lambda: tr("&Check Well-formedness"),
            f"{_ACTIONS}:check",
            "Ctrl+Alt+Shift+K",
            languages=_XML,
            icon="circle-check",
        ),
        CommandSpec(
            "xml.xpath",
            lambda: tr("Evaluate &XPath..."),
            f"{_ACTIONS}:show_xpath",
            separator_before=True,
            languages=_XML,
            icon="search-code",
        ),
        CommandSpec(
            "xml.autoclose",
            lambda: tr("&Auto-close Tags"),
            "forge.tools.xml_tool.autoclose:toggled",
            checked_setting="autoclose",
            separator_before=True,
        ),
    ),
    on_startup="forge.tools.xml_tool.autoclose:install",
    defaults={"autoclose": True},
)

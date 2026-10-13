"""Markdown editing helpers: emphasis, headings, lists, links, code and tables."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

_ACTIONS = "forge.tools.markdown_tool.actions"
_MD = ("markdown",)

EXTENSION = ExtensionInfo(
    id="forge.markdown",
    title=lambda: tr("Mar&kdown"),
    placement="language",
    commands=(
        CommandSpec(
            "markdown.bold",
            lambda: tr("&Bold"),
            f"{_ACTIONS}:bold",
            "Ctrl+B",
            languages=_MD,
            icon="bold",
        ),
        CommandSpec(
            "markdown.italic",
            lambda: tr("&Italic"),
            f"{_ACTIONS}:italic",
            "Ctrl+I",
            languages=_MD,
            icon="italic",
        ),
        CommandSpec(
            "markdown.code",
            lambda: tr("Inline &Code"),
            f"{_ACTIONS}:inline_code",
            languages=_MD,
            icon="code",
        ),
        CommandSpec(
            "markdown.link",
            lambda: tr("&Link"),
            f"{_ACTIONS}:link",
            languages=_MD,
            icon="link",
        ),
        CommandSpec(
            "markdown.heading",
            lambda: tr("&Heading"),
            f"{_ACTIONS}:heading",
            separator_before=True,
            languages=_MD,
            icon="heading",
            tooltip=lambda: tr("Heading (click again for the next level)"),
        ),
        CommandSpec(
            "markdown.quote",
            lambda: tr("&Quote"),
            f"{_ACTIONS}:quote",
            languages=_MD,
            icon="text-quote",
        ),
        CommandSpec(
            "markdown.bullets",
            lambda: tr("B&ulleted List"),
            f"{_ACTIONS}:bullets",
            languages=_MD,
            icon="list",
        ),
        CommandSpec(
            "markdown.numbers",
            lambda: tr("&Numbered List"),
            f"{_ACTIONS}:numbers",
            languages=_MD,
            icon="list-ordered",
        ),
        CommandSpec(
            "markdown.tasks",
            lambda: tr("&Task List"),
            f"{_ACTIONS}:tasks",
            languages=_MD,
            icon="list-checks",
        ),
        CommandSpec(
            "markdown.code_block",
            lambda: tr("Code Bl&ock"),
            f"{_ACTIONS}:code_block",
            separator_before=True,
            languages=_MD,
            icon="square-code",
        ),
        CommandSpec(
            "markdown.table",
            lambda: tr("T&able"),
            f"{_ACTIONS}:table",
            languages=_MD,
            icon="table",
        ),
        CommandSpec(
            "markdown.rule",
            lambda: tr("Horizontal &Rule"),
            f"{_ACTIONS}:rule",
            languages=_MD,
            icon="minus",
        ),
    ),
)

"""Find in Files: search and replace across a folder (Notepad++ Search > Find in Files)."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

EXTENSION = ExtensionInfo(
    id="forge.find_in_files",
    title=lambda: tr("Find in Files"),
    placement="search",
    commands=(
        CommandSpec(
            "find_in_files.open",
            lambda: tr("Find &in Files..."),
            "forge.tools.find_in_files.panel:open_panel",
            "Ctrl+Shift+F",
        ),
    ),
)

"""Static description of an extension: its menu entries and handlers.

Everything here is cheap to import. Handlers are referenced as
``"package.module:function"`` strings and imported on first use, so heavy
libraries (lxml, yaml, difflib views) never slow down Forge's start.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

Text = Callable[[], str]  # translated lazily, after the UI language is installed


@dataclass(frozen=True)
class CommandSpec:
    id: str
    title: Text
    handler: str  # "module:function", called as function(api)
    shortcut: str | None = None
    # Checkable commands show a check mark read from this setting key
    # (stored per extension, see ForgeAPI.setting).
    checked_setting: str | None = None
    separator_before: bool = False
    # Shown as a button on the document toolbar for documents in these
    # languages (by language id). ``icon`` is a bundled Lucide icon name.
    languages: tuple[str, ...] = ()
    icon: str | None = None
    # Tooltip for the toolbar button; defaults to the title without "&" and "...".
    tooltip: Text | None = None
    # Also in the editor's right-click menu, under the extension's title:
    # "selection" only when text is selected, "always" in every case.
    context: str | None = None


@dataclass(frozen=True)
class ExtensionInfo:
    id: str
    title: Text
    commands: tuple[CommandSpec, ...] = ()
    # "tools": a submenu under Tools; "tools-flat": directly in Tools;
    # "search": appended to the Search menu (Notepad++ puts Find in Files there).
    placement: str = "tools"
    # A separator above this extension's entry in its menu.
    separator_before: bool = False
    # Optional "module:function" called once after the window is shown.
    on_startup: str | None = None
    defaults: dict[str, object] = field(default_factory=dict)

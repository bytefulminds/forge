"""Loads the built-in tools into the menus and runs them safely.

Menus are built from each tool's static ``ExtensionInfo``; a tool's code is
imported the first time one of its commands runs. Every call into a tool is
wrapped: an exception is logged and shown as a notice, Forge keeps running.
"""

from __future__ import annotations

import importlib
import logging
from collections import defaultdict
from collections.abc import Callable
from functools import partial
from typing import Any

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMenu

from forge.extensions.api import ForgeAPI
from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr
from forge.ui.document_toolbar import ToolItem

log = logging.getLogger(__name__)


def _tooltip(spec: CommandSpec) -> str:
    text = spec.tooltip() if spec.tooltip else spec.title().replace("&", "").rstrip(".")
    if spec.shortcut:
        native = QKeySequence(spec.shortcut).toString(QKeySequence.SequenceFormat.NativeText)
        text = f"{text} ({native})"
    return text


def builtin_extensions() -> list[ExtensionInfo]:
    from forge.tools import (
        compare,
        csv_tool,
        find_in_files,
        json_tool,
        markdown_tool,
        xml_tool,
        yaml_tool,
    )

    return [
        json_tool.EXTENSION,
        yaml_tool.EXTENSION,
        xml_tool.EXTENSION,
        markdown_tool.EXTENSION,
        csv_tool.EXTENSION,
        compare.EXTENSION,
        find_in_files.EXTENSION,
    ]


class ExtensionEvents:
    def __init__(self, report: Callable[[str, Exception], None]) -> None:
        self._handlers: dict[str, list[tuple[str, Callable[..., None]]]] = defaultdict(list)
        self._report = report

    def subscribe(self, event: str, callback: Callable[..., None], extension_id: str) -> None:
        self._handlers[event].append((extension_id, callback))

    def has(self, event: str) -> bool:
        return bool(self._handlers.get(event))

    def emit(self, event: str, *args: Any) -> None:
        for extension_id, callback in list(self._handlers.get(event, [])):
            try:
                callback(*args)
            except Exception as exc:
                self._report(extension_id, exc)


class ExtensionHost:
    def __init__(self, window: Any) -> None:
        self._window = window
        self.extensions = builtin_extensions()
        self._by_id = {ext.id: ext for ext in self.extensions}
        self._apis: dict[str, ForgeAPI] = {}
        self.actions: dict[str, QAction] = {}
        self.events = ExtensionEvents(self.report_error)

    def api(self, extension_id: str) -> ForgeAPI:
        if extension_id not in self._apis:
            self._apis[extension_id] = ForgeAPI(self._window, extension_id)
        return self._apis[extension_id]

    # Menus -------------------------------------------------------------------

    def build_menus(self, tools_menu: QMenu, search_menu: QMenu) -> None:
        for ext in self.extensions:
            if ext.placement == "search":
                search_menu.addSeparator()
                target = search_menu
            elif ext.placement == "tools-flat":
                tools_menu.addSeparator()
                target = tools_menu
            else:
                submenu = tools_menu.addMenu(ext.title())
                assert submenu is not None
                target = submenu
            for spec in ext.commands:
                if spec.separator_before:
                    target.addSeparator()
                target.addAction(self._make_action(ext, spec))

    def _make_action(self, ext: ExtensionInfo, spec: CommandSpec) -> QAction:
        action = QAction(spec.title(), self._window)
        action.setMenuRole(QAction.MenuRole.NoRole)
        if spec.shortcut:
            action.setShortcut(QKeySequence(spec.shortcut))
        if spec.checked_setting:
            action.setCheckable(True)
            default = ext.defaults.get(spec.checked_setting, False)
            api = self.api(ext.id)
            action.setChecked(bool(api.setting(spec.checked_setting, default)))
            action.toggled.connect(lambda checked, e=ext, s=spec: self._toggle(e, s, checked))
        else:
            action.triggered.connect(lambda _c=False, e=ext, s=spec: self.run(e, s))
        self.actions[spec.id] = action
        return action

    def _toggle(self, ext: ExtensionInfo, spec: CommandSpec, checked: bool) -> None:
        assert spec.checked_setting is not None
        self.api(ext.id).set_setting(spec.checked_setting, checked)
        self.run(ext, spec)

    # Document toolbar ----------------------------------------------------------

    def toolbar_items(self, language_id: str) -> list[ToolItem]:
        """Buttons for the document toolbar of a document in ``language_id``."""
        items: list[ToolItem] = []
        for ext in self.extensions:
            for spec in ext.commands:
                if language_id not in spec.languages or not spec.icon:
                    continue
                items.append(
                    ToolItem(
                        key=spec.id,
                        icon=spec.icon,
                        tooltip=_tooltip(spec),
                        run=partial(self.run, ext, spec),
                        separator_before=spec.separator_before and bool(items),
                    )
                )
        return items

    # Running -----------------------------------------------------------------

    def run_command(self, command_id: str) -> None:
        for ext in self.extensions:
            for spec in ext.commands:
                if spec.id == command_id:
                    self.run(ext, spec)
                    return
        raise KeyError(command_id)

    def run(self, ext: ExtensionInfo, spec: CommandSpec) -> None:
        self._call(ext.id, spec.handler)
        # A tool may have changed the document's state (delimiter, language).
        refresh = getattr(self._window, "refresh_current_tab", None)
        if refresh is not None:
            refresh()

    def start(self) -> None:
        for ext in self.extensions:
            if ext.on_startup:
                self._call(ext.id, ext.on_startup)

    def _call(self, extension_id: str, target: str) -> None:
        try:
            module_name, _, function_name = target.partition(":")
            function = getattr(importlib.import_module(module_name), function_name)
            function(self.api(extension_id))
        except Exception as exc:
            self.report_error(extension_id, exc)

    def report_error(self, extension_id: str, exc: Exception) -> None:
        log.exception("Tool %s failed", extension_id, exc_info=exc)
        ext = self._by_id.get(extension_id)
        name = ext.title() if ext else extension_id
        self._window.status.showMessage(
            tr("{tool} ran into a problem: {error}", tool=name, error=str(exc)), 8000
        )

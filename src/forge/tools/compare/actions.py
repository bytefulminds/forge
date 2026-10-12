"""Compare commands."""

from __future__ import annotations

import contextlib

from PyQt6.QtWidgets import QInputDialog

from forge.core.fileio import load_text
from forge.extensions.api import EditorHandle, ForgeAPI, tr
from forge.themes.theme import Theme
from forge.tools.compare.view import CompareView


def _show(
    api: ForgeAPI, left: str, right: str, left_title: str, right_title: str, tab_title: str
) -> None:
    view = CompareView(api, left, right, left_title, right_title)
    comparison = view.comparison
    api.on("theme_changed", lambda theme: _retheme(view, theme))
    api.add_tab(view, tab_title)
    if comparison.identical:
        api.status(tr("No differences."))
    else:
        view.jump(1)


def _retheme(view: CompareView, theme: Theme) -> None:
    with contextlib.suppress(RuntimeError):  # the view was closed
        view.apply_theme(theme)


def compare_with_saved(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None or editor.path is None:
        api.status(tr("Save the document first; there is no saved version to compare with."))
        return
    try:
        saved = load_text(editor.path).text
    except OSError as exc:
        api.status(tr("Could not read {name}: {error}", name=editor.title, error=str(exc)))
        return
    _show(
        api,
        saved,
        editor.text(),
        tr("{name} (saved)", name=editor.title),
        editor.title,
        tr("Changes in {name}", name=editor.title),
    )


def compare_with_tab(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None:
        return
    others: list[EditorHandle] = [e for e in api.editors() if not e.is_same(editor)]
    if not others:
        api.status(tr("Open a second document to compare with."))
        return
    other = others[0]
    if len(others) > 1:
        titles = [e.title for e in others]
        choice, ok = QInputDialog.getItem(
            api.window, tr("Compare with Tab"), tr("Compare with:"), titles, 0, False
        )
        if not ok:
            return
        other = others[titles.index(choice)]
    # The other tab is the "old" side, the current tab the "new" side: lines
    # you added in this tab show green on the right. Swap Sides turns it around.
    _show(
        api,
        other.text(),
        editor.text(),
        other.title,
        editor.title,
        f"{other.title} \u2194 {editor.title}",
    )

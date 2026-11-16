"""Utility window commands (the windows load on first use)."""

from __future__ import annotations

from forge.extensions.api import ForgeAPI


def regex_tester(api: ForgeAPI) -> None:
    from forge.tools.utilities.regex_tester import open_regex_tester

    open_regex_tester(api)


def code_shot(api: ForgeAPI) -> None:
    from forge.tools.utilities.codeshot import open_code_shot

    editor = api.active_editor()
    if editor is not None:
        open_code_shot(api, editor)


def snipping_tool(api: ForgeAPI) -> None:
    from forge.tools.utilities.snipping import open_snipping_tool

    open_snipping_tool(api)

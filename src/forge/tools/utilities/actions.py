"""Utility window commands (the windows load on first use)."""

from __future__ import annotations

from forge.extensions.api import ForgeAPI, tr

DEFAULT_SNIP_KEY = "Ctrl+Alt+Shift+S"


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


def snip_now(api: ForgeAPI) -> None:
    """A snip without the options window (global shortcut, ``forge --snip``)."""
    from forge.tools.utilities.snipping import snip_now as start

    start(api)


def register_global_shortcut(api: ForgeAPI) -> None:
    """Make the snip shortcut work system-wide, as set in Preferences."""
    enabled = bool(api.setting("global_snip", True))
    key = str(api.setting("global_snip_key", DEFAULT_SNIP_KEY) or "")
    problem = api.set_global_shortcut("snip", key if enabled else None, lambda: snip_now(api))
    if not problem or problem == "unsupported":
        return  # Wayland: Preferences explains forge --snip
    if problem == "taken":
        message = tr(
            "Another program already uses {key}, so it does not start the Snipping Tool "
            "outside Forge. Choose another key in Preferences.",
            key=key,
        )
    else:
        message = tr("The global shortcut {key} does not work: {reason}", key=key, reason=problem)
    api.notify(message, "warning")


def startup(api: ForgeAPI) -> None:
    register_global_shortcut(api)
    api.on("settings_changed", lambda: register_global_shortcut(api))

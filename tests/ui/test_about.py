from __future__ import annotations

from pytestqt.qtbot import QtBot

from forge import __version__
from forge.themes.theme import get_theme
from forge.ui.about_dialog import AboutDialog, system_info


def test_about_shows_version_and_copies_system_info(qtbot: QtBot) -> None:
    dialog = AboutDialog(get_theme("dark", True))
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "About Forge"
    info = system_info()
    assert f"Forge {__version__}" in info and "Qt " in info and "Settings:" in info
    dialog.copy_button.click()
    assert dialog.copy_button.text() == "Copied"
    assert dialog.height() > 300  # wrapped text fits (height follows the width)

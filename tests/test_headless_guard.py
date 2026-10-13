"""The test run must never wait for a click: unpatched dialogs fail at once."""

from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from forge.ui.message_box import Button, FramedMessageBox


def test_unpatched_dialog_fails_instead_of_blocking(qtbot: QtBot) -> None:
    box = FramedMessageBox("question", "Forge", "Save?", Button.Yes | Button.No)
    qtbot.addWidget(box)
    with pytest.raises(AssertionError, match="FramedMessageBox"):
        box.exec()

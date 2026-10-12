from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QMessageBox

from forge.ui import message_box


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Modal dialogs would block a headless test run; answer them automatically."""
    monkeypatch.setattr(
        message_box, "question", lambda *_a, **_k: QMessageBox.StandardButton.Discard
    )
    for name in ("warning", "information", "critical", "about"):
        monkeypatch.setattr(message_box, name, lambda *_a, **_k: QMessageBox.StandardButton.Ok)

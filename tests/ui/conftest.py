from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QMessageBox


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Modal dialogs would block a headless test run; answer them automatically."""
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_a, **_k: QMessageBox.StandardButton.Discard
    )
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, lambda *_a, **_k: QMessageBox.StandardButton.Ok)

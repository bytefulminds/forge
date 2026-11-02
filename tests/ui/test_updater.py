"""The updater against a fake release served from files (file:// URLs)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from forge import __version__
from forge.core import updates
from forge.core.settings import Settings
from forge.ui import message_box, updater
from forge.ui.main_window import MainWindow


def make_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def fake_release(
    folder: Path, version: str, package: bytes = b"new forge", checksum: str | None = None
) -> Path:
    """A release JSON with one AppImage and its .sha256 next to it."""
    name = f"Forge-{version}-linux-x86_64.AppImage"
    (folder / name).write_bytes(package)
    digest = checksum or hashlib.sha256(package).hexdigest()
    (folder / f"{name}.sha256").write_text(f"{digest}  {name}\n")
    release = {
        "tag_name": f"v{version}",
        "description": "### Added\n\n- Something new.",
        "_links": {"self": "https://gitlab.com/bytefulminds/forge/-/releases"},
        "assets": {"links": [{"name": name, "url": (folder / name).as_uri()}]},
    }
    path = folder / "latest.json"
    path.write_text(json.dumps(release))
    return path


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    folder = tmp_path / "release"
    folder.mkdir()

    def publish(version: str, **kwargs: object) -> None:
        path = fake_release(folder, version, **kwargs)  # type: ignore[arg-type]
        monkeypatch.setenv("FORGE_UPDATE_URL", path.as_uri())

    return publish


def test_automatic_check_offers_a_newer_version(qtbot: QtBot, server: Callable[..., None]) -> None:
    server("99.0.0")
    window = make_window(qtbot)
    window.updater.check(manual=False)
    qtbot.waitUntil(lambda: window.updater.bar.isVisibleTo(window), timeout=5000)
    assert window.updater.bar.label.text() == "Forge 99.0.0 is available."
    assert window.settings.updates.last_check
    texts = [b.text() for b in window.updater.bar.buttons]
    assert texts == ["Download", "What's New"]  # tests run from source: no install


def test_skipped_and_current_versions_stay_quiet(
    qtbot: QtBot, server: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    server("99.0.0")
    window = make_window(qtbot)
    window.settings.updates.skipped_version = "99.0.0"
    window.updater.check(manual=False)
    qtbot.waitUntil(lambda: bool(window.settings.updates.last_check), timeout=5000)
    assert not window.updater.bar.isVisibleTo(window)

    server(__version__)
    told: list[str] = []
    monkeypatch.setattr(message_box, "information", lambda _p, _t, text, *a: told.append(text))
    window.updater.check(manual=True)
    qtbot.waitUntil(lambda: bool(told), timeout=5000)
    assert told[0] == f"You have the latest version of Forge ({__version__})."


def test_manual_check_reports_errors(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("<html>maintenance</html>")
    monkeypatch.setenv("FORGE_UPDATE_URL", broken.as_uri())
    window = make_window(qtbot)
    warned: list[str] = []
    monkeypatch.setattr(message_box, "warning", lambda _p, _t, text, *a: warned.append(text))
    window.updater.check(manual=True)
    qtbot.waitUntil(lambda: bool(warned), timeout=5000)
    assert warned[0].startswith("Forge could not check for updates")


def _appimage_window(
    qtbot: QtBot,
    server: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    **kw: object,
) -> tuple[MainWindow, Path, list[Callable[[], None]]]:
    server("99.0.0", **kw)
    installed = tmp_path / "apps" / "Forge.AppImage"
    installed.parent.mkdir()
    installed.write_bytes(b"old forge")
    monkeypatch.setenv("APPIMAGE", str(installed))
    window = make_window(qtbot)
    window.updater.kind = updates.APPIMAGE
    restarts: list[Callable[[], None]] = []
    monkeypatch.setattr(
        window.updater, "restart_with", lambda start: restarts.append(start) or True
    )
    window.updater.check(manual=False)
    qtbot.waitUntil(lambda: window.updater.release is not None, timeout=5000)
    return window, installed, restarts


def test_install_replaces_the_appimage_and_restarts(
    qtbot: QtBot, server: Callable[..., None], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window, installed, restarts = _appimage_window(qtbot, server, monkeypatch, tmp_path)
    assert window.updater.bar.buttons[0].text() == "Install and Restart"
    dialog = updater.UpdateDialog(window.updater, window.updater.release)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)
    dialog.install()
    qtbot.waitUntil(lambda: bool(restarts), timeout=10_000)
    assert installed.read_bytes() == b"new forge"


def test_a_damaged_download_is_not_installed(
    qtbot: QtBot, server: Callable[..., None], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window, installed, restarts = _appimage_window(
        qtbot, server, monkeypatch, tmp_path, checksum="0" * 64
    )
    dialog = updater.UpdateDialog(window.updater, window.updater.release)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)
    dialog.install()
    qtbot.waitUntil(lambda: "damaged" in dialog.status.text(), timeout=10_000)
    assert installed.read_bytes() == b"old forge"
    assert not restarts
    assert dialog.install_button.isEnabled()


def test_preferences_switch_turns_automatic_checks_off(qtbot: QtBot) -> None:
    from forge.ui.preferences import PreferencesDialog

    window = make_window(qtbot)
    dialog = PreferencesDialog(window.settings, window.apply_settings, window)
    qtbot.addWidget(dialog)
    assert dialog.check_updates.isChecked()
    dialog.check_updates.setChecked(False)
    assert window.settings.updates.check_automatically is False

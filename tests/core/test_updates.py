from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from forge.core import installer, updates

RELEASE = {
    "tag_name": "v0.2.0",
    "description": "### Added\n\n- An updater.",
    "_links": {"self": "https://gitlab.com/bytefulminds/forge/-/releases/v0.2.0"},
    "assets": {
        "links": [
            {"name": "macOS", "url": "https://x/forge/0.2.0/Forge-0.2.0-macos-arm64.dmg"},
            {"name": "Linux", "url": "https://x/forge/0.2.0/Forge-0.2.0-linux-x86_64.AppImage"},
            {"name": "Windows", "url": "https://x/forge/0.2.0/Forge-0.2.0-setup.exe"},
        ]
    },
}


def test_versions_compare_as_numbers() -> None:
    assert updates.parse_version("v1.10.2") == (1, 10, 2)
    assert updates.parse_version("1.2") is None
    assert updates.is_newer("v0.10.0", "0.9.9")
    assert not updates.is_newer("0.1.0", "0.1.0")
    assert not updates.is_newer("garbage", "0.1.0")


def test_release_and_download_per_installation() -> None:
    release = updates.parse_release(RELEASE)
    assert release.version == "0.2.0"
    assert release.notes.startswith("### Added")
    assert release.page_url.endswith("/releases/v0.2.0")
    assert release.download_for(updates.WINDOWS_INSTALLER).endswith("-setup.exe")  # type: ignore[union-attr]
    assert release.download_for(updates.APPIMAGE).endswith(".AppImage")  # type: ignore[union-attr]
    assert release.download_for(updates.MACOS_APP).endswith(".dmg")  # type: ignore[union-attr]
    assert release.download_for(None) is None
    with pytest.raises(updates.UpdateError):
        updates.parse_release({"tag_name": "latest"})
    with pytest.raises(updates.UpdateError):
        updates.parse_release(["not", "a", "release"])


def test_installation_kind() -> None:
    kind = updates.installation_kind
    assert kind("linux", frozen=False, environ={}) is None  # from source
    assert kind("win32", frozen=True, environ={}) == updates.WINDOWS_INSTALLER
    assert kind("linux", frozen=True, environ={"APPIMAGE": "/a/Forge.AppImage"}) == updates.APPIMAGE
    assert kind("linux", frozen=True, environ={}) is None  # unpacked build
    mac = "/Applications/Forge.app/Contents/MacOS/Forge"
    assert kind("darwin", frozen=True, executable=mac, environ={}) == updates.MACOS_APP
    assert updates.macos_app_bundle(mac) == Path("/Applications/Forge.app")


def test_checksums(tmp_path: Path) -> None:
    file = tmp_path / "Forge.AppImage"
    file.write_bytes(b"forge")
    digest = hashlib.sha256(b"forge").hexdigest()
    assert updates.parse_checksum(f"{digest.upper()}  Forge.AppImage\n") == digest
    updates.verify(file, digest)
    with pytest.raises(updates.UpdateError, match="damaged"):
        updates.verify(file, "0" * 64)
    with pytest.raises(updates.UpdateError):
        updates.parse_checksum("<html>not found</html>")
    assert updates.checksum_url("https://x/a.dmg?ref=1") == "https://x/a.dmg.sha256?ref=1"


def test_check_is_due_once_a_day() -> None:
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    assert updates.check_due("", now)
    assert updates.check_due((now - timedelta(hours=25)).isoformat(), now)
    assert not updates.check_due((now - timedelta(hours=2)).isoformat(), now)
    assert updates.check_due((now + timedelta(days=3)).isoformat(), now)  # clock was wrong


def test_replace_appimage(tmp_path: Path) -> None:
    target = tmp_path / "Forge.AppImage"
    target.write_bytes(b"old")
    download = tmp_path / "download"
    download.write_bytes(b"new")
    installer.replace_appimage(download, target)
    assert target.read_bytes() == b"new"
    assert os.access(target, os.X_OK)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Forge.AppImage", "download"]


def test_windows_setup_runs_silently_and_restarts() -> None:
    command = installer.windows_setup_command(Path("C:/Temp/Forge-0.2.0-setup.exe"))
    assert "/SILENT" in command and "/restart=1" in command


def test_clean_environment_drops_what_this_process_was_given() -> None:
    env = installer.clean_environment(
        {
            "APPIMAGE": "/x",
            "LD_LIBRARY_PATH": "/bundle",
            "LD_LIBRARY_PATH_ORIG": "/usr/lib",
            "HOME": "/h",
        }
    )
    assert env == {"LD_LIBRARY_PATH": "/usr/lib", "HOME": "/h"}


def test_stage_macos_app_copies_out_of_the_disk_image(tmp_path: Path) -> None:
    app = tmp_path / "Forge.app"
    app.mkdir()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(command)
        if command[:2] == ["hdiutil", "attach"]:
            mount = Path(command[command.index("-mountpoint") + 1])
            (mount / "Forge.app" / "Contents").mkdir(parents=True)
        if command[0] == "ditto":
            Path(command[2]).mkdir()
        return subprocess.CompletedProcess(command, 0)

    staged = installer.stage_macos_app(tmp_path / "Forge.dmg", app, fake_run)
    assert staged == tmp_path / ".Forge-update.app" and staged.is_dir()
    assert [c[0] for c in calls] == ["hdiutil", "ditto", "hdiutil"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell script")
def test_macos_swap_script_swaps_and_opens(tmp_path: Path) -> None:
    app, staged = tmp_path / "Forge.app", tmp_path / ".Forge-update.app"
    app.mkdir()
    (app / "old").touch()
    staged.mkdir()
    (staged / "new").touch()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    opened = tmp_path / "opened"
    (bin_dir / "open").write_text(f'#!/bin/sh\necho "$1" > {opened}\n')
    (bin_dir / "open").chmod(0o755)
    script = installer.write_swap_script(
        app, staged, pid=2**22 + 12345
    )  # no such process: Forge has quit
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    subprocess.run([str(script)], check=True, env=env, timeout=10)
    assert (app / "new").exists() and not staged.exists()
    assert not (tmp_path / ".Forge-old.app").exists()
    assert opened.read_text().strip() == str(app)
    assert not script.exists()

from __future__ import annotations

import os
from pathlib import Path

from pytestqt.qtbot import QtBot

from forge.core.watcher import FileWatcher


def _touch_later(path: Path, text: str) -> None:
    path.write_text(text)
    stat = path.stat()
    # Make sure the timestamp moves even on coarse file systems.
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


def test_reports_external_change(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("one")
    watcher = FileWatcher()
    watcher.watch(file)
    with qtbot.waitSignal(watcher.changed, timeout=3000) as blocker:
        _touch_later(file, "two")
    assert blocker.args == [file]


def test_ignores_own_writes(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("one")
    watcher = FileWatcher()
    watcher.watch(file)
    _touch_later(file, "mine")
    watcher.remember(file)
    with qtbot.assertNotEmitted(watcher.changed, wait=600):
        watcher.check_all()


def test_reports_deletion(qtbot: QtBot, tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_text("one")
    watcher = FileWatcher()
    watcher.watch(file)
    with qtbot.waitSignal(watcher.deleted, timeout=3000):
        file.unlink()

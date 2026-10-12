"""Detect changes made to open files by other programs.

QFileSystemWatcher reports every write, including Forge's own saves, and stops
watching a path once a program replaces the file atomically. ``FileWatcher``
re-arms the watch after each event, debounces bursts of events, and compares
the file's modification time and size with what Forge last read or wrote, so
it only reports real external changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

DEBOUNCE_MS = 250


@dataclass(frozen=True)
class FileStamp:
    mtime_ns: int
    size: int


def stamp(path: Path) -> FileStamp | None:
    try:
        info = os.stat(path)
    except OSError:
        return None
    return FileStamp(info.st_mtime_ns, info.st_size)


class FileWatcher(QObject):
    changed = pyqtSignal(object)  # Path: modified by another program
    deleted = pyqtSignal(object)  # Path: removed or renamed away

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_event)
        self._stamps: dict[Path, FileStamp | None] = {}
        self._pending: set[Path] = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self._flush)

    def watch(self, path: Path) -> None:
        """Start watching ``path`` and treat its current state as known."""
        self._stamps[path] = stamp(path)
        self._arm(path)

    def unwatch(self, path: Path) -> None:
        self._stamps.pop(path, None)
        self._pending.discard(path)
        if str(path) in self._watcher.files():
            self._watcher.removePath(str(path))

    def remember(self, path: Path) -> None:
        """Forge just read or wrote ``path``: its current state is not a change."""
        if path in self._stamps:
            self._stamps[path] = stamp(path)
            self._arm(path)

    def check_all(self) -> None:
        """Compare every watched file now (used when the window regains focus)."""
        self._pending.update(self._stamps)
        self._flush()

    def _arm(self, path: Path) -> None:
        if path.exists() and str(path) not in self._watcher.files():
            self._watcher.addPath(str(path))

    def _on_event(self, name: str) -> None:
        self._pending.add(Path(name))
        self._timer.start()

    def _flush(self) -> None:
        pending, self._pending = self._pending, set()
        for path in pending:
            if path not in self._stamps:
                continue
            known = self._stamps[path]
            current = stamp(path)
            self._arm(path)
            if current == known:
                continue
            self._stamps[path] = current
            if current is None:
                self.deleted.emit(path)
            else:
                self.changed.emit(path)

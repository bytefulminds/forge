"""Session snapshot: open tabs, unsaved text and the active tab.

Like Notepad++, Forge does not ask about unsaved changes when it quits. It
writes every tab (including unsaved and untitled text) to the session folder
in the platform cache directory and restores it on the next start. The
snapshot is also refreshed periodically, so a crash loses at most a few
seconds of typing.

Layout of ``<cache>/session/``::

    session.json        tabs, their order and the active tab
    backup/<name>.txt   UTF-8 text of tabs with unsaved content
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from forge.core import paths

log = logging.getLogger(__name__)

SESSION_VERSION = 1


@dataclass
class TabState:
    path: str | None = None
    untitled_index: int = 0
    codec: str = "utf-8"
    bom: bool = False
    eol: str = "LF"
    language: str = "text"
    dirty: bool = False
    # File name in the backup folder holding the unsaved text, if any.
    backup: str | None = None
    cursor_line: int = 0
    cursor_index: int = 0
    first_visible_line: int = 0
    # "text", "split" or "preview" (Markdown, CSV and JSON documents).
    view_mode: str = "text"


@dataclass
class SessionState:
    tabs: list[TabState] = field(default_factory=list)
    active: int = 0
    version: int = SESSION_VERSION


def session_dir() -> Path:
    path = paths.cache_dir() / "session"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_dir() -> Path:
    path = session_dir() / "backup"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def save_session(state: SessionState, backups: dict[str, str]) -> None:
    """Write backup texts first, then the session file, then drop stale backups.

    ``backups`` maps backup file names (as referenced by ``TabState.backup``)
    to their text.
    """
    backup_dir = _backup_dir()
    for name, text in backups.items():
        _atomic_write(backup_dir / name, text.encode("utf-8"))
    payload = json.dumps(asdict(state), indent=2, ensure_ascii=False)
    _atomic_write(session_dir() / "session.json", payload.encode("utf-8"))
    referenced = {tab.backup for tab in state.tabs if tab.backup}
    for file in backup_dir.iterdir():
        if file.is_file() and file.name not in referenced:
            file.unlink(missing_ok=True)


def load_session() -> SessionState:
    """Return the saved session, or an empty one when missing or unreadable."""
    file = session_dir() / "session.json"
    if not file.exists():
        return SessionState()
    try:
        raw: Any = json.loads(file.read_text(encoding="utf-8"))
        tabs = [_tab_from_raw(item) for item in raw.get("tabs", [])]
        active = int(raw.get("active", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        log.exception("Could not read session %s, starting empty", file)
        return SessionState()
    return SessionState(tabs=tabs, active=active)


def _tab_from_raw(raw: Any) -> TabState:
    if not isinstance(raw, dict):
        raise TypeError("tab entry is not an object")
    defaults = TabState()
    values = {
        key: raw[key]
        for key in asdict(defaults)
        if key in raw and (raw[key] is None or isinstance(raw[key], (str, int, bool)))
    }
    return TabState(**values)


def read_backup(name: str) -> str | None:
    file = _backup_dir() / name
    try:
        return file.read_text(encoding="utf-8")
    except OSError:
        log.warning("Backup %s is missing", file)
        return None

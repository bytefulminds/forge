from __future__ import annotations

from pathlib import Path

from forge.core.session import (
    SessionState,
    TabState,
    load_session,
    read_backup,
    save_session,
    session_dir,
)


def test_round_trip_and_stale_backups_are_removed(forge_home: Path) -> None:
    state = SessionState(
        tabs=[
            TabState(path="/tmp/a.py", language="python"),
            TabState(untitled_index=2, dirty=True, backup="tab-2.txt", cursor_line=3),
        ],
        active=1,
    )
    save_session(state, {"tab-2.txt": "unsaved ✓"})
    (session_dir() / "backup" / "old.txt").write_text("stale", newline="")
    save_session(state, {"tab-2.txt": "unsaved ✓"})

    loaded = load_session()
    assert loaded == state
    assert read_backup("tab-2.txt") == "unsaved ✓"
    assert not (session_dir() / "backup" / "old.txt").exists()


def test_missing_or_corrupt_session_is_empty(forge_home: Path) -> None:
    assert load_session() == SessionState()
    (session_dir() / "session.json").write_text("{not json", newline="")
    assert load_session() == SessionState()

"""Installing a downloaded, verified update (no Qt).

- Windows: the Inno Setup installer runs silently, closes Forge if needed and
  starts it again (``/restart=1``, see packaging/windows/forge.iss).
- Linux: the AppImage file is replaced; the running copy keeps working until
  Forge restarts.
- macOS: the new Forge.app is copied out of the disk image next to the
  current one while Forge runs; a small script swaps the two once Forge has
  quit and opens the new app.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from forge.core.updates import UpdateError

Run = Callable[..., subprocess.CompletedProcess[bytes]]

# Set by PyInstaller and AppRun for this process; a new Forge sets its own.
_INHERITED = ("APPIMAGE", "APPDIR", "ARGV0", "OWD", "QTWEBENGINE_DISABLE_SANDBOX", "_MEIPASS2")


def clean_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for a new Forge, without what this one was given."""
    env = dict(os.environ if environ is None else environ)
    for key in _INHERITED:
        env.pop(key, None)
    for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(f"{key}_ORIG", None)
        if original is not None:
            env[key] = original
        else:
            env.pop(key, None)
    return env


def launch_detached(command: list[str]) -> None:
    """Start ``command`` so that it outlives Forge."""
    options: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": clean_environment(),
        "close_fds": True,
    }
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        options["creationflags"] = flags
    else:
        options["start_new_session"] = True
    subprocess.Popen(command, **options)  # type: ignore[call-overload]


def writable(folder: Path) -> bool:
    return os.access(folder, os.W_OK)


# Windows ----------------------------------------------------------------------------


def windows_setup_command(setup: Path) -> list[str]:
    """Inno Setup without questions; it closes Forge and starts it again."""
    return [
        str(setup),
        "/SILENT",
        "/SP-",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/restart=1",
    ]


# Linux --------------------------------------------------------------------------------


def replace_appimage(download: Path, target: Path) -> None:
    """Put ``download`` in place of the AppImage at ``target``.

    The new file is copied next to the old one first, so the final step is
    an atomic rename on the same file system.
    """
    if not writable(target.parent):
        raise UpdateError(f"Forge cannot write to {target.parent}")
    staging = target.with_name(f".{target.name}.update")
    shutil.copyfile(download, staging)
    os.chmod(staging, 0o755)
    os.replace(staging, target)


# macOS ----------------------------------------------------------------------------------


def stage_macos_app(dmg: Path, app: Path, run: Run = subprocess.run) -> Path:
    """Copy Forge.app from ``dmg`` next to ``app``; returns the staged copy."""
    if not writable(app.parent):
        raise UpdateError(f"Forge cannot write to {app.parent}")
    staged = app.with_name(f".{app.stem}-update.app")
    mount = Path(tempfile.mkdtemp(prefix="forge-update-"))
    try:
        run(
            ["hdiutil", "attach", "-nobrowse", "-readonly", "-noautoopen",
             "-mountpoint", str(mount), str(dmg)],
            check=True, capture_output=True,
        )  # fmt: skip
        try:
            source = mount / "Forge.app"
            if not source.is_dir():
                raise UpdateError("the disk image holds no Forge.app")
            if staged.exists():
                shutil.rmtree(staged)
            run(["ditto", str(source), str(staged)], check=True, capture_output=True)
        finally:
            run(["hdiutil", "detach", str(mount), "-quiet"], check=False, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise UpdateError(f"{exc.cmd[0]} failed") from exc
    finally:
        shutil.rmtree(mount, ignore_errors=True)
    return staged


def macos_swap_script(app: Path, staged: Path, pid: int) -> str:
    """Shell script: wait for Forge to quit, swap the apps, open the new one.
    If the swap fails the old app is put back."""
    old = app.with_name(f".{app.stem}-old.app")
    a, s, o = shlex.quote(str(app)), shlex.quote(str(staged)), shlex.quote(str(old))
    return f"""#!/bin/sh
while kill -0 {pid} 2>/dev/null; do sleep 0.2; done
rm -rf {o}
if mv {a} {o}; then
  if mv {s} {a}; then
    rm -rf {o}
  else
    mv {o} {a}
  fi
fi
open {a}
rm -f "$0"
"""


def write_swap_script(app: Path, staged: Path, pid: int) -> Path:
    handle, name = tempfile.mkstemp(prefix="forge-update-", suffix=".sh")
    with os.fdopen(handle, "w", encoding="utf-8") as script:
        script.write(macos_swap_script(app, staged, pid))
    os.chmod(name, 0o755)
    return Path(name)

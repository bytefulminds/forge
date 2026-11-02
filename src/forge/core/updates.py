"""Updates (no Qt): which release is newest, which download fits this
installation, and whether a download is intact.

Forge asks GitLab for the latest release of the project. The release links
point at the packages in the project's package registry; next to every
package CI publishes ``<package>.sha256`` (see .gitlab-ci.yml), which is
checked before anything is installed.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# The latest release of gitlab.com/bytefulminds/forge.
RELEASES_API = "https://gitlab.com/api/v4/projects/bytefulminds%2Fforge/releases/permalink/latest"
CHECK_INTERVAL = timedelta(hours=24)

# How this copy of Forge was installed, which decides how it can update itself.
WINDOWS_INSTALLER = "windows-installer"
APPIMAGE = "appimage"
MACOS_APP = "macos-app"

_ASSET_SUFFIX = {
    WINDOWS_INSTALLER: "-setup.exe",
    APPIMAGE: "-linux-x86_64.AppImage",
    MACOS_APP: "-macos-arm64.dmg",
}
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateError(Exception):
    pass


def releases_url() -> str:
    """The release endpoint; ``FORGE_UPDATE_URL`` points elsewhere for testing
    (a ``file://`` URL to a JSON file works too)."""
    return os.environ.get("FORGE_UPDATE_URL") or RELEASES_API


def automatic_checks_allowed() -> bool:
    """Off in the test suite and the smoke test (``FORGE_NO_UPDATE_CHECK=1``)."""
    return not os.environ.get("FORGE_NO_UPDATE_CHECK")


def parse_version(text: str) -> tuple[int, int, int] | None:
    match = _VERSION.match(text.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def is_newer(candidate: str, current: str) -> bool:
    new, old = parse_version(candidate), parse_version(current)
    return new is not None and old is not None and new > old


@dataclass(frozen=True)
class Release:
    version: str  # "0.2.0"
    notes: str  # Markdown, from CHANGELOG.md
    page_url: str  # the release on GitLab
    downloads: tuple[str, ...] = field(default_factory=tuple)

    def download_for(self, kind: str | None) -> str | None:
        """The package URL that fits ``kind`` (see installation_kind)."""
        suffix = _ASSET_SUFFIX.get(kind or "")
        if suffix is None:
            return None
        for url in self.downloads:
            if url.split("?")[0].endswith(suffix):
                return url
        return None


def parse_release(data: Any) -> Release:
    """A Release from the GitLab releases API (one release object)."""
    if not isinstance(data, dict):
        raise UpdateError("unexpected answer from the release server")
    tag = str(data.get("tag_name", ""))
    version = parse_version(tag)
    if version is None:
        raise UpdateError(f"release tag {tag!r} is not a version")
    links = (data.get("assets") or {}).get("links") or []
    downloads = tuple(
        str(link.get("url") or link.get("direct_asset_url"))
        for link in links
        if isinstance(link, dict) and (link.get("url") or link.get("direct_asset_url"))
    )
    page = (data.get("_links") or {}).get("self") or ""
    return Release(
        version=".".join(str(part) for part in version),
        notes=str(data.get("description") or ""),
        page_url=str(page),
        downloads=downloads,
    )


def installation_kind(
    platform: str = sys.platform,
    frozen: bool | None = None,
    executable: str = sys.executable,
    environ: dict[str, str] | None = None,
) -> str | None:
    """How Forge was installed, or ``None`` when it runs from source (which
    cannot update itself; it only points at the release page)."""
    environ = dict(os.environ) if environ is None else environ
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not frozen:
        return None
    if platform == "win32":
        return WINDOWS_INSTALLER
    if platform.startswith("linux") and environ.get("APPIMAGE"):
        return APPIMAGE
    if platform == "darwin" and macos_app_bundle(executable) is not None:
        return MACOS_APP
    return None


def macos_app_bundle(executable: str = sys.executable) -> Path | None:
    """``/Applications/Forge.app`` for ``.../Forge.app/Contents/MacOS/Forge``."""
    path = Path(executable)
    for parent in path.parents:
        if parent.suffix == ".app":
            return parent
    return None


def checksum_url(download_url: str) -> str:
    base, _, query = download_url.partition("?")
    return f"{base}.sha256" + (f"?{query}" if query else "")


def parse_checksum(text: str) -> str:
    """The SHA-256 from a ``.sha256`` file: the hex digest, optionally followed
    by the file name (``sha256sum`` style)."""
    first = text.strip().split()[0] if text.strip() else ""
    if not _SHA256.match(first):
        raise UpdateError("the checksum file does not hold a SHA-256")
    return first.lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected.lower():
        raise UpdateError("the download is damaged (its checksum does not match)")


def check_due(last_check: str, now: datetime | None = None) -> bool:
    """True when the last automatic check (ISO 8601, may be empty) is a day old."""
    now = now or datetime.now(UTC)
    try:
        last = datetime.fromisoformat(last_check)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return now - last >= CHECK_INTERVAL or last > now

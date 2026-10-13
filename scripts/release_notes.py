"""Print the release notes for a tag, after checking the versions agree.

    python scripts/release_notes.py v0.1.0        # notes for that tag
    python scripts/release_notes.py --version     # the version, e.g. 0.1.0

The tag must be ``v`` plus the version in ``src/forge/__init__.py``, which must
equal the version in ``pyproject.toml``, and ``CHANGELOG.md`` must have a
section for it. Otherwise the script exits with 1 and says what is wrong, so a
release with mismatched numbers cannot be published.

Standard library only: the release job runs it without installing Forge.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_URL = "https://gitlab.com/bytefulminds/forge"

INSTALL_NOTES = """\
### Install

- **macOS (Apple Silicon, macOS 11 or later):** open the `.dmg` and drag Forge to
  Applications. The app is not notarized by Apple yet, so macOS blocks the first start:
  open *System Settings > Privacy & Security* and click *Open Anyway* (on macOS 14 and
  earlier, right-click Forge in Applications and choose *Open*).
- **Linux (x86-64):** make the `.AppImage` executable (`chmod +x`) and run it.
- **Windows (x86-64):** run the setup. Windows SmartScreen may warn about an unknown
  publisher: choose *More info* and then *Run anyway*.

See the [manual]({repository}/-/blob/v{version}/MANUAL.md) for every feature.
"""


class ReleaseError(Exception):
    pass


def package_version(root: Path = ROOT) -> str:
    text = (root / "src" / "forge" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"$', text, re.MULTILINE)
    if match is None:
        raise ReleaseError("No __version__ in src/forge/__init__.py")
    return match.group(1)


def project_version(root: Path = ROOT) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def checked_version(root: Path = ROOT) -> str:
    version = package_version(root)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ReleaseError(f"Version {version!r} is not MAJOR.MINOR.PATCH")
    other = project_version(root)
    if other != version:
        raise ReleaseError(f"pyproject.toml says {other} but src/forge/__init__.py says {version}")
    return version


def changelog_section(version: str, root: Path = ROOT) -> str:
    """The text under ``## [version]`` up to the next ``## `` heading."""
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\n]*$", re.MULTILINE)
    match = heading.search(text)
    if match is None:
        raise ReleaseError(f"CHANGELOG.md has no section '## [{version}]'")
    rest = text[match.end() :]
    following = re.search(r"^## ", rest, re.MULTILINE)
    body = rest[: following.start()] if following else rest
    body = body.strip()
    if not body:
        raise ReleaseError(f"The CHANGELOG.md section for {version} is empty")
    return body


def release_notes(tag: str, root: Path = ROOT) -> str:
    version = checked_version(root)
    if tag != f"v{version}":
        raise ReleaseError(f"Tag {tag} does not match version {version} (expected v{version})")
    body = changelog_section(version, root)
    install = INSTALL_NOTES.format(repository=REPOSITORY_URL, version=version)
    return f"{body}\n\n{install}"


def main(argv: list[str]) -> int:
    try:
        if argv == ["--version"]:
            print(checked_version())
        elif len(argv) == 1 and not argv[0].startswith("-"):
            print(release_notes(argv[0]), end="")
        else:
            print("usage: release_notes.py vX.Y.Z | --version", file=sys.stderr)
            return 2
    except ReleaseError as exc:
        print(f"release_notes: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

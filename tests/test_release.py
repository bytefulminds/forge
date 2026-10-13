"""Release checks: versions agree and the changelog has notes for this version."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

import forge

ROOT = Path(__file__).resolve().parent.parent


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "release_notes", ROOT / "scripts" / "release_notes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_notes = _load_script()


def test_versions_agree() -> None:
    assert release_notes.checked_version() == forge.__version__
    assert release_notes.project_version() == forge.__version__


def test_changelog_has_this_version() -> None:
    notes = release_notes.release_notes(f"v{forge.__version__}")
    assert "### Install" in notes
    assert f"/-/blob/v{forge.__version__}/MANUAL.md" in notes
    assert "## [" not in notes  # only this version's section


def test_wrong_tag_is_refused() -> None:
    with pytest.raises(release_notes.ReleaseError, match="does not match"):
        release_notes.release_notes("v99.0.0")


def _copy_project(tmp_path: Path) -> Path:
    (tmp_path / "src" / "forge").mkdir(parents=True)
    shutil.copy(ROOT / "src" / "forge" / "__init__.py", tmp_path / "src" / "forge")
    shutil.copy(ROOT / "pyproject.toml", tmp_path)
    shutil.copy(ROOT / "CHANGELOG.md", tmp_path)
    return tmp_path


def test_mismatched_pyproject_is_refused(tmp_path: Path) -> None:
    root = _copy_project(tmp_path)
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        text.replace(f'version = "{forge.__version__}"', 'version = "9.9.9"', 1), encoding="utf-8"
    )
    with pytest.raises(release_notes.ReleaseError, match=r"pyproject\.toml says 9\.9\.9"):
        release_notes.checked_version(root)


def test_missing_changelog_section_is_refused(tmp_path: Path) -> None:
    root = _copy_project(tmp_path)
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## [0.0.1] - 2020-01-01\n\n- old\n")
    with pytest.raises(release_notes.ReleaseError, match="no section"):
        release_notes.changelog_section(forge.__version__, root)


def test_section_stops_at_the_next_version(tmp_path: Path) -> None:
    root = _copy_project(tmp_path)
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [2.0.0] - 2030-01-01\n\n- new\n\n## [1.0.0] - 2029-01-01\n\n- old\n"
    )
    assert release_notes.changelog_section("2.0.0", root) == "- new"
    assert release_notes.changelog_section("1.0.0", root) == "- old"

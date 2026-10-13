"""The checks behind ``forge --smoke-test`` pass from a source checkout too."""

from __future__ import annotations

from forge import smoke


def test_flag_is_recognised() -> None:
    assert smoke.requested(["forge", "--smoke-test"])
    assert not smoke.requested(["forge", "notes.md"])


def test_bundled_resources_are_found() -> None:
    assert "languages" in smoke._check_resources()


def test_every_tool_module_imports() -> None:
    assert smoke._check_tool_modules().endswith("modules")

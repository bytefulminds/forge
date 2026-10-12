"""Translation catalogs.

Forge uses simple TOML catalogs (``resources/i18n/<lang>.toml``) that map the
English source string to its translation. English is the source language and
needs no catalog. Qt's own dialogs (file dialogs, message box buttons) are
translated with the ``.qm`` files that ship with Qt itself.

Why not Qt Linguist ``.ts``/``.qm`` for our own strings: the ``lrelease`` tool
that compiles them is not part of the PyQt6 wheels, and a plain TOML catalog
keeps the toolchain pure Python.
"""

from __future__ import annotations

import ast
import tomllib
from importlib import resources
from pathlib import Path

SOURCE_LANGUAGE = "en"

# Language code -> native name, shown in the language menu.
LANGUAGES: dict[str, str] = {
    "en": "English",
    "nl": "Nederlands",
}


def load_catalog(language: str) -> dict[str, str]:
    if language == SOURCE_LANGUAGE:
        return {}
    resource = resources.files("forge.resources.i18n").joinpath(f"{language}.toml")
    if not resource.is_file():
        return {}
    data = tomllib.loads(resource.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def find_translatable_strings(root: Path) -> set[str]:
    """Return every string literal passed as first argument to ``tr()`` under ``root``."""
    found: set[str] = set()
    for file in root.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(node.args[0].value)
    return found

"""``forge --smoke-test``: start Forge without a screen, check it works, exit.

Used by the build scripts and CI to verify a packaged build (PyInstaller,
AppImage, macOS app, Windows installer) before it is published. It checks
that the bundled files are present, every tool module imports, a few
documents open with their previews, and, when the browser engine is
bundled, that the rich Markdown preview draws a Mermaid diagram.

Exit code 0 means every check passed. The report goes to stdout and, with
``--smoke-report=FILE``, to that file too (a windowed Windows build has no
console).
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtCore import QObject

FLAG = "--smoke-test"
REPORT_FLAG = "--smoke-report="

_SAMPLES = {
    "notes.md": "# Forge\n\n- [x] works\n\n```mermaid\ngraph LR\n  A-->B\n```\n",
    "data.json": '{"name": "Forge", "tools": ["json", "csv"]}\n',
    "table.csv": "id,name,created\n1,Ada,1700000000\n2,Linus,1700000100\n",
    "script.py": "def hello() -> str:\n    return 'Forge'\n",
}


def requested(argv: list[str]) -> bool:
    return FLAG in argv


def prepare_environment() -> Path:
    """Before QApplication: no screen needed, and no real user settings touched."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if not os.environ.get("FORGE_HOME"):
        os.environ["FORGE_HOME"] = tempfile.mkdtemp(prefix="forge-smoke-")
    # Chromium refuses its sandbox when run as root (CI containers).
    if sys.platform.startswith("linux") and os.geteuid() == 0:
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    return Path(os.environ["FORGE_HOME"])


class _Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed = 0

    def check(self, name: str, test: Callable[[], str | None]) -> None:
        try:
            detail = test()
        except Exception as exc:  # report every failure, then carry on
            self.failed += 1
            self.add(f"FAIL  {name}: {type(exc).__name__}: {exc}")
            return
        self.add(f"ok    {name}" + (f" ({detail})" if detail else ""))

    def add(self, line: str) -> None:
        self.lines.append(line)
        print(line, flush=True)


def _wait_until(condition: Callable[[], bool], seconds: float) -> bool:
    from PyQt6.QtCore import QCoreApplication

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return False


def _delete_now(widget: QObject) -> None:
    """Delete before the app quits: a browser page outliving its profile crashes."""
    from PyQt6.QtCore import QCoreApplication, QEvent

    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    QCoreApplication.processEvents()


def _check_resources() -> str:
    fonts = resources.files("forge.resources.fonts")
    for name in ("Inter-Regular.ttf", "JetBrainsMono-Regular.ttf"):
        if not fonts.joinpath(name).is_file():
            raise FileNotFoundError(name)
    icons = resources.files("forge.resources.icons")
    if not icons.joinpath("forge.svg").is_file():
        raise FileNotFoundError("forge.svg")
    lucide = [p for p in icons.joinpath("lucide").iterdir() if p.name.endswith(".svg")]
    if len(lucide) < 10:
        raise FileNotFoundError(f"only {len(lucide)} Lucide icons")
    if not resources.files("forge.resources.web").joinpath("mermaid.min.js").is_file():
        raise FileNotFoundError("mermaid.min.js")
    from forge.i18n.catalog import LANGUAGES, SOURCE_LANGUAGE, load_catalog

    for language in LANGUAGES:
        if language != SOURCE_LANGUAGE and not load_catalog(language):
            raise FileNotFoundError(f"{language}.toml")
    return f"{len(lucide)} icons, {len(LANGUAGES)} languages"


def _check_tool_modules() -> str:
    from forge.ui.extension_host import builtin_extensions

    modules: set[str] = set()
    for ext in builtin_extensions():
        targets = [spec.handler for spec in ext.commands]
        if ext.on_startup:
            targets.append(ext.on_startup)
        for target in targets:
            module_name, _, function_name = target.partition(":")
            module = importlib.import_module(module_name)
            if not callable(getattr(module, function_name, None)):
                raise AttributeError(target)
            modules.add(module_name)
    return f"{len(modules)} modules"


def _check_documents(window: object, folder: Path) -> str:
    from forge.ui.main_window import MainWindow

    assert isinstance(window, MainWindow)
    for name, text in _SAMPLES.items():
        path = folder / name
        path.write_text(text, encoding="utf-8", newline="")
        if window.open_path(path) is None:
            raise RuntimeError(f"could not open {name}")
    _wait_until(lambda: False, 0.5)
    opened = {tab.doc.path.name for tab in window.all_tabs() if tab.doc.path is not None}
    missing = set(_SAMPLES) - opened
    if missing:
        raise RuntimeError(f"not open: {', '.join(sorted(missing))}")
    return f"{len(opened)} documents"


def _check_web_preview() -> str:
    from forge.ui.previews import rich_markdown_available

    if not rich_markdown_available():
        return "browser engine not bundled, skipped"
    from forge.themes.theme import get_theme
    from forge.ui.web_preview import WebMarkdownPreview

    preview = WebMarkdownPreview(get_theme("dark", True))
    preview.resize(800, 600)
    preview.show()
    preview.show_document(_SAMPLES["notes.md"], None)
    page = preview.web.page()
    assert page is not None
    found: list[object] = []

    def drawn() -> bool:
        page.runJavaScript("document.querySelectorAll('svg').length", found.append)
        return bool(found) and found[-1] == 1

    ok = _wait_until(drawn, 60)
    preview.close()
    _delete_now(preview)
    if not ok:
        raise TimeoutError("the Mermaid diagram was not drawn within 60 seconds")
    return "Mermaid diagram drawn"


def run(window: object, home: Path, argv: list[str]) -> int:
    """Run the checks against the started window; returns the exit code."""
    from forge import __version__

    report = _Report()
    report.add(f"Forge {__version__} smoke test ({sys.platform}, frozen={_frozen()})")
    report.check("bundled resources", _check_resources)
    report.check("tool modules", _check_tool_modules)
    samples = home / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    report.check("open documents", lambda: _check_documents(window, samples))
    report.check("rich Markdown preview", _check_web_preview)
    report.add("PASSED" if report.failed == 0 else f"FAILED ({report.failed})")
    for arg in argv:
        if arg.startswith(REPORT_FLAG):
            Path(arg[len(REPORT_FLAG) :]).write_text("\n".join(report.lines) + "\n", "utf-8")
    return 0 if report.failed == 0 else 1


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))

"""Rich Markdown preview with Qt WebEngine and Mermaid diagrams.

Only imported when PyQt6-WebEngine is installed (``uv sync --extra web``).
The page is loaded once; edits replace its content through JavaScript, so
the scroll position stays put and Mermaid only redraws changed diagrams.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget

from forge.themes.theme import Theme
from forge.ui.markdown_render import mermaid_config, render_body, rich_css
from forge.ui.previews import Preview

_SCRIPT = """
const cache = new Map();
let counter = 0;
let pending = null;
let busy = false;

async function drawDiagrams() {
  const nodes = Array.from(document.querySelectorAll('pre.mermaid'));
  for (const node of nodes) {
    const source = node.textContent;
    let svg = cache.get(source);
    if (svg === undefined) {
      try {
        const result = await mermaid.render('forge-mermaid-' + (counter++), source);
        svg = result.svg;
      } catch (error) {
        svg = null;
        const text = document.createElement('pre');
        text.className = 'mermaid-error';
        text.textContent = String(error.message || error);
        cache.set(source, text.outerHTML);
      }
      if (svg) cache.set(source, svg);
    }
    const out = document.createElement('div');
    out.className = 'mermaid-diagram';
    out.innerHTML = cache.get(source);
    node.replaceWith(out);
  }
  if (cache.size > 200) cache.clear();
}

async function forgeRender(html) {
  pending = html;
  if (busy) return;
  busy = true;
  while (pending !== null) {
    const next = pending;
    pending = null;
    const content = document.getElementById('content');
    content.innerHTML = next;
    document.querySelectorAll('pre.mermaid').forEach(n => n.classList.add('pending'));
    if (window.mermaid) { await drawDiagrams(); }
  }
  busy = false;
}

function forgeScroll(ratio) {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  window.scrollTo(0, Math.max(0, max) * ratio);
}

document.addEventListener('click', event => {
  const link = event.target.closest('a');
  if (!link) return;
  const href = link.getAttribute('href') || '';
  if (href.startsWith('#')) {
    event.preventDefault();
    const target = document.getElementById(decodeURIComponent(href.slice(1)));
    if (target) target.scrollIntoView();
  }
});
"""


CODE_FONT = "JetBrains Mono"
UI_FONT = "Inter"
_FONT_FILES = (
    (UI_FONT, "Inter-Regular.ttf", 400, "normal"),
    (UI_FONT, "Inter-SemiBold.ttf", 600, "normal"),
    (CODE_FONT, "JetBrainsMono-Regular.ttf", 400, "normal"),
    (CODE_FONT, "JetBrainsMono-Bold.ttf", 700, "normal"),
    (CODE_FONT, "JetBrainsMono-Italic.ttf", 400, "italic"),
)


def _resource_url(package: str, name: str) -> QUrl:
    return QUrl.fromLocalFile(str(Path(str(resources.files(package).joinpath(name)))))


def _font_faces() -> str:
    """The bundled fonts, so the preview looks the same without them installed."""
    return "".join(
        f"@font-face {{ font-family: '{family}'; font-weight: {weight}; font-style: {style};"
        f" src: url('{_resource_url('forge.resources.fonts', file).toString()}'); }}\n"
        for family, file, weight, style in _FONT_FILES
    )


def _default_base() -> QUrl:
    """Unsaved documents still need a local base URL to load the bundled files."""
    folder = Path(str(resources.files("forge.resources.web")))
    return QUrl.fromLocalFile(str(folder) + "/")


class _Page(QWebEnginePage):
    """Opens clicked links in the system browser instead of inside the preview."""

    def acceptNavigationRequest(
        self, url: QUrl, kind: QWebEnginePage.NavigationType, is_main_frame: bool
    ) -> bool:
        if kind == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            web = url.scheme() in ("http", "https", "mailto")
            if web or (url.isLocalFile() and Path(url.toLocalFile()).is_file()):
                QDesktopServices.openUrl(url)
            return False
        return super().acceptNavigationRequest(url, kind, is_main_frame)


class WebMarkdownPreview(Preview):
    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        self.web = QWebEngineView()
        self.web.setObjectName("markdownWebPreview")
        page = _Page(self.web)
        self.web.setPage(page)
        settings = page.settings()
        if settings is not None:
            attribute = QWebEngineSettings.WebAttribute
            settings.setAttribute(attribute.LocalContentCanAccessRemoteUrls, False)
            settings.setAttribute(attribute.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(attribute.JavascriptCanOpenWindows, False)
            settings.setAttribute(attribute.JavascriptCanAccessClipboard, False)
        super().__init__(self.web, parent)
        self._theme = theme
        self._ready = False
        self._base = _default_base()
        self._pending: str | None = None
        self._ratio: float | None = None
        self.web.loadFinished.connect(self._on_loaded)
        self._load_shell()

    def _load_shell(self) -> None:
        self._ready = False
        theme = self._theme
        css = _font_faces() + rich_css(theme, CODE_FONT, UI_FONT)
        config = json.dumps(mermaid_config(theme))
        shell = f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>{css}</style>
<script src="{_resource_url("forge.resources.web", "mermaid.min.js").toString()}"></script>
<script>
if (window.mermaid) {{ mermaid.initialize({config}); }}
{_SCRIPT}
</script>
</head><body><div id="content"></div></body></html>"""
        self.web.setHtml(shell, self._base)

    def _on_loaded(self, ok: bool) -> None:
        self._ready = ok
        if ok and self._pending is not None:
            self._push(self._pending)

    def _push(self, body: str) -> None:
        self._pending = body
        if not self._ready:
            return
        page = self.web.page()
        if page is not None:
            page.runJavaScript(f"forgeRender({json.dumps(body)})")
            if self._ratio is not None:
                page.runJavaScript(f"forgeScroll({self._ratio})")

    def show_document(self, text: str, path: Path | None) -> None:
        base = QUrl.fromLocalFile(str(path.parent) + "/") if path is not None else _default_base()
        if base != self._base:
            # Relative images resolve against the document's folder.
            self._base = base
            self._pending = render_body(text, rich=True)
            self._load_shell()
            self.show_view()
            return
        self._push(render_body(text, rich=True))
        self.show_view()

    def apply_theme(self, theme: Theme) -> None:
        self._theme = theme
        self._load_shell()

    def scroll_to_ratio(self, ratio: float) -> None:
        self._ratio = ratio
        page = self.web.page()
        if self._ready and page is not None:
            page.runJavaScript(f"forgeScroll({ratio})")

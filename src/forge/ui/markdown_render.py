"""Markdown to HTML with markdown-it-py (CommonMark plus GitHub-style extras).

Raw HTML in the document is shown as text, never executed. ``mermaid`` code
blocks become diagram placeholders for the rich (WebEngine) preview and stay
code blocks, with a short hint, in the basic preview.
"""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from functools import cache
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from forge.themes.theme import Theme

MERMAID = "mermaid"


@cache
def _parser(rich: bool) -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False})
        .enable(["table", "strikethrough"])
        .use(front_matter_plugin)
        .use(footnote_plugin)
        .use(tasklists_plugin)
        .use(anchors_plugin, max_level=6)
    )

    def fence(
        renderer: RendererHTML,
        tokens: Sequence[Token],
        idx: int,
        options: OptionsDict,
        env: EnvType,
    ) -> str:
        token = tokens[idx]
        language = token.info.strip().split(maxsplit=1)[0].lower() if token.info.strip() else ""
        if language == MERMAID:
            code = html.escape(token.content)
            if rich:
                return f'<pre class="mermaid">{code}</pre>\n'
            return f'<pre class="mermaid-source"><code>{code}</code></pre>\n'
        return RendererHTML.fence(renderer, tokens, idx, options, env)

    md.add_render_rule("fence", fence)
    # Front matter (YAML between --- lines) is metadata, not content.
    md.add_render_rule("front_matter", lambda *_args: "")
    return md


def render_body(text: str, rich: bool) -> str:
    """The document as an HTML fragment."""
    return str(_parser(rich).render(text))


# Basic preview (QTextBrowser) ---------------------------------------------------

_CHECKBOX = re.compile(r'<input class="task-list-item-checkbox"([^>]*)> ?')


def _checkbox(match: re.Match[str]) -> str:
    return "☑ " if "checked" in match.group(1) else "☐ "


def basic_html(text: str, mermaid_hint: str) -> str:
    """HTML for Qt's rich text engine, which knows HTML 4 and a little CSS."""
    body = render_body(text, rich=False)
    body = _CHECKBOX.sub(_checkbox, body)
    body = body.replace("<table>", '<table border="1" cellspacing="0" cellpadding="6">')
    if 'class="mermaid-source"' in body:
        hint = f'<p class="hint">{html.escape(mermaid_hint)}</p>'
        body = body.replace('<pre class="mermaid-source">', f'{hint}<pre class="mermaid-source">')
    return body


def basic_css(theme: Theme, code_font: str) -> str:
    c = theme
    return f"""
    body {{ color: {c.text}; }}
    a {{ color: {c.accent}; text-decoration: none; }}
    h1, h2, h3, h4, h5, h6 {{ color: {c.text}; margin-top: 18px; margin-bottom: 8px; }}
    h1 {{ font-size: 26px; }} h2 {{ font-size: 21px; }} h3 {{ font-size: 17px; }}
    p, li {{ line-height: 140%; }}
    code {{ font-family: "{code_font}"; color: {c.syntax.string};
            background-color: {c.elevated_bg}; }}
    pre {{ font-family: "{code_font}"; background-color: {c.elevated_bg};
           margin-top: 8px; margin-bottom: 8px; padding: 10px; }}
    pre code {{ color: {c.text}; }}
    blockquote {{ color: {c.text_muted}; margin-left: 12px; }}
    table {{ border-color: {c.border}; border-collapse: collapse; margin: 8px 0; }}
    th {{ background-color: {c.elevated_bg}; }}
    hr {{ background-color: {c.border}; }}
    p.hint {{ color: {c.text_muted}; font-size: 12px; margin-bottom: 0; }}
    ul.contains-task-list {{ list-style-type: none; }}
    """


# Rich preview (Qt WebEngine) ----------------------------------------------------


def rich_css(theme: Theme, code_font: str, ui_font: str) -> str:
    c = theme
    return f"""
    :root {{ color-scheme: {"dark" if theme.is_dark else "light"}; }}
    html, body {{ background: {c.editor_bg}; color: {c.text}; margin: 0; }}
    body {{ font-family: "{ui_font}", system-ui, sans-serif; font-size: 15px;
            line-height: 1.6; }}
    #content {{ max-width: 900px; padding: 20px 28px 60px; margin: 0 auto; }}
    a {{ color: {c.accent}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h1, h2, h3, h4, h5, h6 {{ line-height: 1.25; margin: 1.4em 0 0.6em; font-weight: 600; }}
    h1 {{ font-size: 2em; padding-bottom: 0.3em; border-bottom: 1px solid {c.border}; }}
    h2 {{ font-size: 1.5em; padding-bottom: 0.3em; border-bottom: 1px solid {c.border}; }}
    h3 {{ font-size: 1.25em; }}
    #content > :first-child {{ margin-top: 0; }}
    code, pre {{ font-family: "{code_font}", ui-monospace, monospace; font-size: 0.88em; }}
    :not(pre) > code {{ background: {c.elevated_bg}; color: {c.syntax.string};
                        padding: 0.15em 0.35em; border-radius: 5px; }}
    pre {{ background: {c.elevated_bg}; padding: 12px 14px; border-radius: 8px;
           overflow-x: auto; border: 1px solid {c.border}; }}
    blockquote {{ margin: 0 0 1em; padding: 0 1em; color: {c.text_muted};
                  border-left: 3px solid {c.border_strong}; }}
    table {{ border-collapse: collapse; margin: 1em 0; display: block; overflow-x: auto; }}
    th, td {{ border: 1px solid {c.border}; padding: 6px 12px; }}
    th {{ background: {c.elevated_bg}; font-weight: 600; }}
    tr:nth-child(2n) td {{ background: {c.caret_line}; }}
    hr {{ border: none; border-top: 1px solid {c.border}; margin: 1.5em 0; }}
    img {{ max-width: 100%; }}
    ul.contains-task-list {{ list-style: none; padding-left: 1.2em; }}
    .task-list-item-checkbox {{ margin-right: 0.5em; }}
    pre.mermaid {{ background: transparent; border: none; text-align: center; }}
    pre.mermaid.pending {{ color: transparent; }}
    .mermaid-error {{ color: {c.text_muted}; border-color: {c.syntax.string}; }}
    .footnotes {{ color: {c.text_muted}; font-size: 0.9em; }}
    ::selection {{ background: {c.selection}; }}
    ::-webkit-scrollbar {{ width: 12px; height: 12px; background: {c.editor_bg}; }}
    ::-webkit-scrollbar-thumb {{ background: {c.scroll_handle}; border-radius: 6px;
                                 border: 3px solid {c.editor_bg}; min-height: 32px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {c.scroll_handle_hover}; }}
    ::-webkit-scrollbar-corner {{ background: {c.editor_bg}; }}
    """


def mermaid_config(theme: Theme) -> dict[str, Any]:
    c = theme
    return {
        "startOnLoad": False,
        "securityLevel": "strict",
        "theme": "base",
        "themeVariables": {
            "darkMode": theme.is_dark,
            "background": c.editor_bg,
            "primaryColor": c.elevated_bg,
            "primaryTextColor": c.text,
            "primaryBorderColor": c.accent,
            "lineColor": c.text_muted,
            "secondaryColor": c.caret_line,
            "tertiaryColor": c.chrome_bg,
            "textColor": c.text,
            "edgeLabelBackground": c.editor_bg,
            "clusterBkg": c.caret_line,
            "clusterBorder": c.border_strong,
            "noteBkgColor": c.elevated_bg,
            "noteTextColor": c.text,
            "fontFamily": "inherit",
        },
    }

from __future__ import annotations

from forge.themes.theme import get_theme
from forge.ui.markdown_render import basic_css, basic_html, mermaid_config, render_body, rich_css

DOC = """---
title: hidden
---
# Title

| a | b |
|---|---|
| 1 | 2 |

- [x] done
- [ ] open

~~old~~ text[^1]

<script>alert(1)</script>

```mermaid
graph TD; A-->B
```

```python
x = 1 < 2
```

[^1]: A note.
"""


def test_render_supports_github_extras() -> None:
    body = render_body(DOC, rich=True)
    assert 'id="title"' in body  # anchors for in-document links
    assert "<table>" in body and "<s>old</s>" in body
    assert "task-list-item-checkbox" in body
    assert "footnote" in body
    assert "hidden" not in body  # front matter is not content
    assert "<script>" not in body and "&lt;script&gt;" in body  # raw HTML is text
    assert '<pre class="mermaid">graph TD; A--&gt;B\n</pre>' in body
    assert "x = 1 &lt; 2" in body


def test_basic_html_suits_qt_rich_text() -> None:
    body = basic_html(DOC, "HINT")
    assert '<table border="1"' in body
    assert "☑ done" in body and "☐ open" in body
    assert "HINT" in body and 'class="mermaid-source"' in body
    assert 'class="mermaid"' not in body


def test_styles_use_theme_colors() -> None:
    for theme_id in ("dark", "light"):
        theme = get_theme(theme_id, True)
        assert theme.text in basic_css(theme, "Mono")
        assert theme.editor_bg in rich_css(theme, "Mono", "Sans")
        assert mermaid_config(theme)["securityLevel"] == "strict"

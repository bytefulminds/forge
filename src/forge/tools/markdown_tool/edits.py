"""Pure text transformations behind the Markdown commands (no Qt here)."""

from __future__ import annotations

import re

_HEADING = re.compile(r"^(#{1,6}) ")
_NUMBERED = re.compile(r"^(\s*)\d+[.)] ")
_BULLET = re.compile(r"^(\s*)[-*+] (?!\[[ xX]\] )")
_TASK = re.compile(r"^(\s*)[-*+] \[[ xX]\] ")
MAX_HEADING_CYCLE = 3


def toggle_wrap(text: str, marker: str) -> tuple[str, int, int]:
    """Wrap ``text`` in ``marker`` or unwrap it when it already is.

    Returns the new text and the (start, length) of the part to select."""
    size = len(marker)
    if len(text) >= 2 * size and text.startswith(marker) and text.endswith(marker):
        inner = text[size:-size]
        return inner, 0, len(inner)
    return f"{marker}{text}{marker}", size, len(text)


def wrapped_outside(before: str, after: str, marker: str) -> bool:
    """Whether the text around a selection is exactly ``marker`` on both sides
    (so ``*`` does not match the stars of ``**bold**``)."""
    size = len(marker)
    if not (before.endswith(marker) and after.startswith(marker)):
        return False
    char = marker[0]
    outer_before = before[: len(before) - size][-1:]
    outer_after = after[size:][:1]
    return not (outer_before == char and outer_after == char)


def link(text: str) -> tuple[str, int, int]:
    """``[text](url)`` with the url selected, or the label when there is no text."""
    if not text:
        label = "text"
        return f"[{label}](https://)", 1, len(label)
    if re.match(r"^https?://\S+$", text):
        return f"[{text}]({text})", 1, len(text)
    result = f"[{text}](https://)"
    return result, len(text) + 3, len("https://")


def cycle_heading(lines: list[str]) -> list[str]:
    """No heading to ``#``, then ``##``, ``###``, then back to plain text."""
    match = _HEADING.match(lines[0]) if lines else None
    level = len(match.group(1)) if match else 0
    target = 0 if level >= MAX_HEADING_CYCLE else level + 1
    result = []
    for line in lines:
        stripped = _HEADING.sub("", line)
        if not stripped.strip():
            result.append(line)
            continue
        result.append(f"{'#' * target} {stripped}" if target else stripped)
    return result


def toggle_prefix(lines: list[str], prefix: str) -> list[str]:
    """Add ``prefix`` to every non-empty line, or remove it when all have it."""
    content = [line for line in lines if line.strip()]
    if content and all(line.startswith(prefix) for line in content):
        return [line[len(prefix) :] if line.startswith(prefix) else line for line in lines]
    return [f"{prefix}{line}" if line.strip() or len(lines) == 1 else line for line in lines]


def _strip_list(line: str) -> str:
    for pattern in (_TASK, _NUMBERED, _BULLET):
        match = pattern.match(line)
        if match:
            return match.group(1) + line[match.end() :]
    return line


def _toggle_list(lines: list[str], pattern: re.Pattern[str], make: str) -> list[str]:
    content = [line for line in lines if line.strip()]
    if content and all(pattern.match(line) for line in content):
        return [_strip_list(line) for line in lines]
    result = []
    number = 1
    for line in lines:
        if not line.strip() and len(lines) > 1:
            result.append(line)
            continue
        plain = _strip_list(line)
        body = plain.lstrip()
        result.append(f"{plain[: len(plain) - len(body)]}{make.format(n=number)}{body}")
        number += 1
    return result


def toggle_bullets(lines: list[str]) -> list[str]:
    return _toggle_list(lines, _BULLET, "- ")


def toggle_numbers(lines: list[str]) -> list[str]:
    return _toggle_list(lines, _NUMBERED, "{n}. ")


def toggle_tasks(lines: list[str]) -> list[str]:
    return _toggle_list(lines, _TASK, "- [ ] ")


def toggle_code_block(lines: list[str]) -> list[str]:
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return lines[1:-1]
    return ["```", *lines, "```"]


def table(labels: list[str], eol: str = "\n") -> str:
    """A Markdown table with one header cell per label and one empty row."""
    columns = len(labels)
    header = "| " + " | ".join(labels) + " |"
    rule = "| " + " | ".join("---" for _ in range(columns)) + " |"
    row = "| " + " | ".join("   " for _ in range(columns)) + " |"
    return eol.join((header, rule, row))


# Footnotes ----------------------------------------------------------------------

_FOOTNOTE = re.compile(r"\[\^(\d+)\]")


def next_footnote(text: str) -> int:
    """The first unused footnote number (``[^1]``, ``[^2]``, ...)."""
    numbers = [int(n) for n in _FOOTNOTE.findall(text)]
    return max(numbers, default=0) + 1


def footnote_definition(text: str, number: int, eol: str = "\n") -> str:
    """What to append at the end of ``text`` for footnote ``number``."""
    gap = "" if text.endswith(eol * 2) else (eol if text.endswith(eol) else eol * 2)
    return f"{gap}[^{number}]: "


# Table of contents --------------------------------------------------------------

TOC_START = "<!-- toc -->"
TOC_END = "<!-- tocstop -->"
_ATX = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _slug(title: str) -> str:
    """The anchor the preview gives a heading (mdit-py-plugins' slugify)."""
    from mdit_py_plugins.anchors.index import slugify

    return str(slugify(title))


def headings(text: str) -> list[tuple[int, str]]:
    """(level, title) of the ATX headings outside code blocks and front matter."""
    found: list[tuple[int, str]] = []
    fence: str | None = None
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":  # front matter
        for index, line in enumerate(lines[1:], 1):
            if line.strip() in ("---", "..."):
                start = index + 1
                break
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else (fence or marker)
            continue
        if fence is not None:
            continue
        match = _ATX.match(line)
        if match:
            found.append((len(match.group(1)), match.group(2)))
    return found


def table_of_contents(text: str, eol: str = "\n") -> str:
    """A nested list of links to the headings, between markers so it can be
    updated in place later. The document title (a single ``#``) is left out."""
    items = headings(text)
    if sum(1 for level, _ in items if level == 1) == 1:
        items = [(level, title) for level, title in items if level > 1]
    if not items:
        return f"{TOC_START}{eol}{TOC_END}"
    top = min(level for level, _ in items)
    seen: dict[str, int] = {}
    lines = [TOC_START]
    for level, title in items:
        slug = _slug(title)
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchor = slug if count == 0 else f"{slug}-{count}"
        lines.append(f"{'  ' * (level - top)}- [{title}](#{anchor})")
    lines.append(TOC_END)
    return eol.join(lines)


def replace_toc(text: str, toc: str) -> str | None:
    """``text`` with an existing table of contents replaced, or None if there is none."""
    start = text.find(TOC_START)
    end = text.find(TOC_END, start)
    if start < 0 or end < 0:
        return None
    return text[:start] + toc + text[end + len(TOC_END) :]


# Tables ---------------------------------------------------------------------------

_ALIGN = re.compile(r"^\s*:?-+:?\s*$")


def is_table_line(line: str) -> bool:
    return line.strip().startswith("|") or line.count("|") >= 2


def _cells(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells: list[str] = []
    current = ""
    escaped = False
    for char in text:
        if char == "|" and not escaped:
            cells.append(current.strip())
            current = ""
        else:
            current += char
        escaped = char == "\\" and not escaped
    cells.append(current.strip())
    return cells


def format_table(lines: list[str]) -> list[str]:
    """Pad every column of a Markdown table to the same width, keeping the
    alignment colons of the separator row."""
    rows = [_cells(line) for line in lines]
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    separator = next(
        (i for i, row in enumerate(rows) if all(_ALIGN.match(c or "-") for c in row) and i > 0),
        None,
    )
    sizes = [
        max([3] + [len(row[col]) for i, row in enumerate(rows) if i != separator])
        for col in range(width)
    ]
    out: list[str] = []
    for i, row in enumerate(rows):
        if i == separator:
            parts = []
            for col, cell in enumerate(row):
                left, right = cell.startswith(":"), cell.endswith(":") and len(cell) > 1
                dashes = "-" * (sizes[col] - left - right)
                parts.append(f"{':' if left else ''}{dashes}{':' if right else ''}")
        else:
            parts = []
            for col, cell in enumerate(row):
                align = rows[separator][col] if separator is not None else ""
                if align.startswith(":") and align.endswith(":") and len(align) > 1:
                    parts.append(cell.center(sizes[col]))
                elif align.endswith(":") and len(align) > 1:
                    parts.append(cell.rjust(sizes[col]))
                else:
                    parts.append(cell.ljust(sizes[col]))
        out.append("| " + " | ".join(parts) + " |")
    return out

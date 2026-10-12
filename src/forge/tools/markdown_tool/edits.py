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

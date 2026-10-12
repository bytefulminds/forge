"""Visual aids drawn with Scintilla indicators: rainbow brackets, rainbow
indentation, brace match highlight and error squiggles.

Indicators leave the lexer's styling alone, so they combine freely with
syntax highlighting.
"""

from __future__ import annotations

import bisect
import re

from PyQt6.Qsci import QsciLexer, QsciScintilla
from PyQt6.QtGui import QColor

from forge.editor.lexers import role_for_description
from forge.themes.theme import Theme

_Q = QsciScintilla

# Indicator numbers (8 is the find highlight, 9 compare inline changes).
BRACKET_INDICATORS = (10, 11, 12)
BRACKET_UNMATCHED = 13
INDENT_INDICATORS = (14, 15, 16, 17)
BRACE_MATCH = 18
BRACE_BAD = 19
DIAGNOSTIC = 20

# Skip documents larger than this for the rainbow passes.
MAX_DECORATED_BYTES = 2_000_000

_BRACKETS = re.compile(rb"[\[\]{}()]")
_PAIRS = {ord(")"): ord("("), ord("]"): ord("["), ord("}"): ord("{")}
_OPENERS = {ord("("), ord("["), ord("{")}


def setup_indicators(editor: QsciScintilla, theme: Theme) -> None:
    """Define colors and styles for every decoration indicator."""
    send = editor.SendScintilla
    rainbow = theme.rainbow or (theme.accent,)
    for i, indicator in enumerate(BRACKET_INDICATORS):
        send(_Q.SCI_INDICSETSTYLE, indicator, _Q.INDIC_TEXTFORE)
        send(_Q.SCI_INDICSETFORE, indicator, QColor(rainbow[i % len(rainbow)]))
    send(_Q.SCI_INDICSETSTYLE, BRACKET_UNMATCHED, _Q.INDIC_TEXTFORE)
    send(_Q.SCI_INDICSETFORE, BRACKET_UNMATCHED, QColor(theme.error))

    tints = theme.indent_rainbow or (theme.accent,)
    for i, indicator in enumerate(INDENT_INDICATORS):
        send(_Q.SCI_INDICSETSTYLE, indicator, _Q.INDIC_STRAIGHTBOX)
        send(_Q.SCI_INDICSETFORE, indicator, QColor(tints[i % len(tints)]))
        send(_Q.SCI_INDICSETALPHA, indicator, 28 if theme.is_dark else 38)
        send(_Q.SCI_INDICSETOUTLINEALPHA, indicator, 0)
        send(_Q.SCI_INDICSETUNDER, indicator, 1)

    # Brace matching as a box under the brace: the brace keeps its own
    # (rainbow) color instead of a style that can wash it out.
    send(_Q.SCI_INDICSETSTYLE, BRACE_MATCH, _Q.INDIC_STRAIGHTBOX)
    send(_Q.SCI_INDICSETFORE, BRACE_MATCH, QColor(theme.accent))
    send(_Q.SCI_INDICSETALPHA, BRACE_MATCH, 70)
    send(_Q.SCI_INDICSETOUTLINEALPHA, BRACE_MATCH, 200)
    send(_Q.SCI_INDICSETUNDER, BRACE_MATCH, 1)
    send(_Q.SCI_BRACEHIGHLIGHTINDICATOR, 1, BRACE_MATCH)
    send(_Q.SCI_INDICSETSTYLE, BRACE_BAD, _Q.INDIC_SQUIGGLE)
    send(_Q.SCI_INDICSETFORE, BRACE_BAD, QColor(theme.error))
    send(_Q.SCI_BRACEBADLIGHTINDICATOR, 1, BRACE_BAD)

    send(_Q.SCI_INDICSETSTYLE, DIAGNOSTIC, _Q.INDIC_SQUIGGLE)
    send(_Q.SCI_INDICSETFORE, DIAGNOSTIC, QColor(theme.error))


def _clear(editor: QsciScintilla, indicators: tuple[int, ...], length: int) -> None:
    for indicator in indicators:
        editor.SendScintilla(_Q.SCI_SETINDICATORCURRENT, indicator)
        editor.SendScintilla(_Q.SCI_INDICATORCLEARRANGE, 0, length)


def _document(editor: QsciScintilla) -> tuple[bytes, int]:
    length = int(editor.SendScintilla(_Q.SCI_GETLENGTH))
    # QsciScintilla.bytes() appends a terminating NUL: cut to the length.
    return bytes(editor.bytes(0, length).data())[:length], length


def skipped_styles(lexer: QsciLexer | None) -> set[int]:
    """Lexer styles for strings and comments, where brackets do not count."""
    if lexer is None:
        return set()
    styles: set[int] = set()
    for style in range(128):
        description = lexer.description(style)
        if description and role_for_description(description) in ("string", "comment"):
            styles.add(style)
    return styles


def bracket_levels(data: bytes) -> list[tuple[int, int]]:
    """(position, level) for every bracket in ``data``; level -1 means unmatched.

    Brackets inside strings and comments must be blanked out by the caller.
    """
    result: list[tuple[int, int]] = []
    stack: list[tuple[int, int, int]] = []  # (char, position, index in result)
    for match in _BRACKETS.finditer(data):
        position = match.start()
        char = data[position]
        if char in _OPENERS:
            stack.append((char, position, len(result)))
            result.append((position, len(stack) - 1))
        elif stack and stack[-1][0] == _PAIRS[char]:
            stack.pop()
            result.append((position, len(stack)))
        else:
            result.append((position, -1))
    for _, position, index in stack:
        result[index] = (position, -1)
    return result


# Documents up to this size skip brackets in strings and comments exactly
# (lexer styles); larger ones blank double-quoted strings with a fast regex.
EXACT_BRACKET_BYTES = 300_000
_DOUBLE_QUOTED = re.compile(rb'"(?:\\.|[^"\\\n])*"')
# Lines painted above and below the visible part of the document.
WINDOW_MARGIN_LINES = 200


def compute_brackets(editor: QsciScintilla, lexer: QsciLexer | None) -> list[tuple[int, int]]:
    """Bracket levels for the whole document (painting happens per window)."""
    data, length = _document(editor)
    if length > MAX_DECORATED_BYTES:
        return []
    skip = skipped_styles(lexer)
    if skip and length <= EXACT_BRACKET_BYTES:
        editor.SendScintilla(_Q.SCI_COLOURISE, 0, -1)
        kept = bytearray(data)
        for match in _BRACKETS.finditer(data):
            position = match.start()
            if int(editor.SendScintilla(_Q.SCI_GETSTYLEAT, position)) in skip:
                kept[position] = 0x20  # blank out: does not count
        data = bytes(kept)
    elif skip:
        data = _DOUBLE_QUOTED.sub(lambda m: b" " * len(m.group(0)), data)
    return bracket_levels(data)


def visible_window(editor: QsciScintilla) -> tuple[int, int, int, int]:
    """(first line, last line, start byte, end byte) of the visible part plus a margin."""
    first_visible = int(editor.SendScintilla(_Q.SCI_GETFIRSTVISIBLELINE))
    first_doc = int(editor.SendScintilla(_Q.SCI_DOCLINEFROMVISIBLE, first_visible))
    on_screen = int(editor.SendScintilla(_Q.SCI_LINESONSCREEN))
    first = max(0, first_doc - WINDOW_MARGIN_LINES)
    last = min(int(editor.lines()) - 1, first_doc + on_screen + WINDOW_MARGIN_LINES)
    start = int(editor.SendScintilla(_Q.SCI_POSITIONFROMLINE, first))
    end = int(editor.SendScintilla(_Q.SCI_GETLINEENDPOSITION, max(first, last)))
    return first, last, start, end


def paint_window(
    editor: QsciScintilla,
    brackets: list[tuple[int, int]],
    tab_width: int,
    show_brackets: bool,
    show_indentation: bool,
) -> None:
    """Paint rainbow brackets and indentation for the visible window only."""
    length = int(editor.SendScintilla(_Q.SCI_GETLENGTH))
    _clear(editor, (*BRACKET_INDICATORS, BRACKET_UNMATCHED, *INDENT_INDICATORS), length)
    if length == 0 or length > MAX_DECORATED_BYTES:
        return
    _first, _last, start, end = visible_window(editor)
    if show_brackets and brackets:
        lo = bisect.bisect_left(brackets, (start, -2))
        hi = bisect.bisect_left(brackets, (end + 1, -2))
        for position, level in brackets[lo:hi]:
            if level < 0:
                indicator = BRACKET_UNMATCHED
            else:
                indicator = BRACKET_INDICATORS[level % len(BRACKET_INDICATORS)]
            editor.SendScintilla(_Q.SCI_SETINDICATORCURRENT, indicator)
            editor.SendScintilla(_Q.SCI_INDICATORFILLRANGE, position, 1)
    if show_indentation:
        data = bytes(editor.bytes(start, end).data())[: end - start]
        for range_start, size, level in indent_ranges(data, tab_width):
            indicator = INDENT_INDICATORS[level % len(INDENT_INDICATORS)]
            editor.SendScintilla(_Q.SCI_SETINDICATORCURRENT, indicator)
            editor.SendScintilla(_Q.SCI_INDICATORFILLRANGE, start + range_start, size)


def indent_ranges(data: bytes, tab_width: int) -> list[tuple[int, int, int]]:
    """(start, length, level) ranges covering each indentation unit."""
    ranges: list[tuple[int, int, int]] = []
    width = max(1, tab_width)
    position = 0
    for line in data.split(b"\n"):
        stripped = line.lstrip(b" \t")
        if stripped.strip(b"\r"):  # leave blank lines alone
            column = 0
            run_start = position
            run_level = 0
            for offset, char in enumerate(line[: len(line) - len(stripped)]):
                level = column // width
                if level != run_level and offset > 0:
                    ranges.append((run_start, position + offset - run_start, run_level))
                    run_start = position + offset
                run_level = level
                column = (column // width + 1) * width if char == 0x09 else column + 1
            indent_bytes = len(line) - len(stripped)
            if indent_bytes:
                ranges.append((run_start, position + indent_bytes - run_start, run_level))
        position += len(line) + 1
    return ranges

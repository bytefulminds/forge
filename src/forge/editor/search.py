"""Find and replace inside one editor, using Scintilla's own search.

Scintilla works in UTF-8 byte positions, so searching through it (instead of
Python's ``re`` on ``editor.text()``) keeps every position valid for
selections and highlights, and never copies a large document into a Python
string. Regular expressions use the ECMAScript flavour (C++11 regex), with
``\\1`` style groups in replacements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PyQt6.Qsci import QsciScintilla

_Q = QsciScintilla

# Scintilla returns -2 from SCI_SEARCHINTARGET for an invalid regular expression.
_INVALID_REGEX = -2
_NOT_FOUND = -1
HIGHLIGHT_INDICATOR = 8  # first indicator number reserved for containers


@dataclass(frozen=True)
class SearchOptions:
    match_case: bool = False
    whole_word: bool = False
    regex: bool = False

    def flags(self) -> int:
        flags = 0
        if self.match_case:
            flags |= _Q.SCFIND_MATCHCASE
        if self.whole_word:
            flags |= _Q.SCFIND_WHOLEWORD
        if self.regex:
            flags |= _Q.SCFIND_REGEXP | _Q.SCFIND_CXX11REGEX
        return flags


class InvalidPattern(ValueError):
    """The regular expression could not be compiled."""


Match = tuple[int, int]  # (start, end) byte positions


def _search(editor: QsciScintilla, query: bytes, start: int, end: int, flags: int) -> Match | None:
    editor.SendScintilla(_Q.SCI_SETSEARCHFLAGS, flags)
    editor.SendScintilla(_Q.SCI_SETTARGETSTART, start)
    editor.SendScintilla(_Q.SCI_SETTARGETEND, end)
    found = editor.SendScintilla(_Q.SCI_SEARCHINTARGET, len(query), query)
    if found == _INVALID_REGEX:
        raise InvalidPattern(query.decode("utf-8", errors="replace"))
    if found == _NOT_FOUND:
        return None
    return found, editor.SendScintilla(_Q.SCI_GETTARGETEND)


def _check_pattern(text: str, options: SearchOptions) -> None:
    """Raise InvalidPattern for a broken regular expression.

    Scintilla reports a broken pattern simply as "not found", so when a regex
    search finds nothing the pattern is compiled with Python's re to tell the
    two apart. Python and ECMAScript syntax agree on everything that commonly
    goes wrong (unbalanced groups and brackets, dangling quantifiers).
    """
    if not options.regex:
        return
    try:
        re.compile(text)
    except re.error as exc:
        raise InvalidPattern(str(exc)) from exc


def _length(editor: QsciScintilla) -> int:
    return int(editor.SendScintilla(_Q.SCI_GETLENGTH))


def find(
    editor: QsciScintilla, text: str, options: SearchOptions, forward: bool = True
) -> Match | None:
    """Find the next (or previous) match after the selection, wrapping around.

    Selects and reveals the match. Returns None when there is no match.
    """
    if not text:
        return None
    query = text.encode("utf-8")
    flags = options.flags()
    length = _length(editor)
    sel_start = int(editor.SendScintilla(_Q.SCI_GETSELECTIONSTART))
    sel_end = int(editor.SendScintilla(_Q.SCI_GETSELECTIONEND))
    if forward:
        # Searching from sel_end; an empty selection would find itself again.
        origin = sel_end if sel_end > sel_start else sel_start
        match = _search(editor, query, origin, length, flags)
        if match is not None and match == (sel_start, sel_end) and sel_end == origin:
            match = _search(editor, query, origin + 1, length, flags) if origin < length else None
        if match is None:
            match = _search(editor, query, 0, length, flags)
    else:
        match = _search(editor, query, sel_start, 0, flags)
        if match is None:
            match = _search(editor, query, length, 0, flags)
    if match is not None:
        select(editor, match)
    else:
        _check_pattern(text, options)
    return match


def select(editor: QsciScintilla, match: Match) -> None:
    start, end = match
    editor.SendScintilla(_Q.SCI_SETSEL, start, end)
    # Keep some context around the match, like Notepad++.
    editor.SendScintilla(_Q.SCI_SCROLLRANGE, end, start)


def find_all(
    editor: QsciScintilla, text: str, options: SearchOptions, limit: int = 0
) -> list[Match]:
    """All matches in document order; stops after ``limit`` matches when given."""
    if not text:
        return []
    query = text.encode("utf-8")
    flags = options.flags()
    length = _length(editor)
    matches: list[Match] = []
    position = 0
    while position <= length:
        match = _search(editor, query, position, length, flags)
        if match is None:
            break
        matches.append(match)
        if limit and len(matches) >= limit:
            break
        start, end = match
        # Zero-length regex matches (like ^) must still move forward.
        position = end if end > start else int(editor.SendScintilla(_Q.SCI_POSITIONAFTER, end))
        if end == start and position == end:
            break
    if not matches:
        _check_pattern(text, options)
    return matches


def replace_current(
    editor: QsciScintilla, text: str, replacement: str, options: SearchOptions
) -> Match | None:
    """Replace the selection if it is a match, then select the next match."""
    query = text.encode("utf-8")
    sel_start = int(editor.SendScintilla(_Q.SCI_GETSELECTIONSTART))
    sel_end = int(editor.SendScintilla(_Q.SCI_GETSELECTIONEND))
    if text and sel_end > sel_start:
        match = _search(editor, query, sel_start, sel_end, options.flags())
        if match == (sel_start, sel_end):
            _replace_target(editor, replacement, options)
            new_end = int(editor.SendScintilla(_Q.SCI_GETTARGETEND))
            editor.SendScintilla(_Q.SCI_SETSEL, new_end, new_end)
    return find(editor, text, options, forward=True)


def replace_all(editor: QsciScintilla, text: str, replacement: str, options: SearchOptions) -> int:
    """Replace every match in the document as one undo step. Returns the count."""
    if not text:
        return 0
    query = text.encode("utf-8")
    flags = options.flags()
    count = 0
    position = 0
    editor.beginUndoAction()
    try:
        while True:
            length = _length(editor)
            if position > length:
                break
            match = _search(editor, query, position, length, flags)
            if match is None:
                break
            start, end = match
            _replace_target(editor, replacement, options)
            count += 1
            new_end = int(editor.SendScintilla(_Q.SCI_GETTARGETEND))
            if end == start:  # zero-length match: step over one character
                if new_end >= _length(editor):
                    break
                new_end = int(editor.SendScintilla(_Q.SCI_POSITIONAFTER, new_end))
            position = new_end
    finally:
        editor.endUndoAction()
    return count


def _replace_target(editor: QsciScintilla, replacement: str, options: SearchOptions) -> None:
    data = replacement.encode("utf-8")
    message = _Q.SCI_REPLACETARGETRE if options.regex else _Q.SCI_REPLACETARGET
    editor.SendScintilla(message, len(data), data)


def highlight(editor: QsciScintilla, matches: list[Match]) -> None:
    clear_highlight(editor)
    editor.SendScintilla(_Q.SCI_SETINDICATORCURRENT, HIGHLIGHT_INDICATOR)
    for start, end in matches:
        if end > start:
            editor.SendScintilla(_Q.SCI_INDICATORFILLRANGE, start, end - start)


def clear_highlight(editor: QsciScintilla) -> None:
    editor.SendScintilla(_Q.SCI_SETINDICATORCURRENT, HIGHLIGHT_INDICATOR)
    editor.SendScintilla(_Q.SCI_INDICATORCLEARRANGE, 0, _length(editor))


def go_to_line(editor: QsciScintilla, line: int) -> None:
    """Move the caret to 1-based ``line`` and center it in the view."""
    last = max(0, int(editor.lines()) - 1)
    target = max(0, min(last, line - 1))
    editor.SendScintilla(_Q.SCI_ENSUREVISIBLEENFORCEPOLICY, target)
    editor.SendScintilla(_Q.SCI_GOTOLINE, target)
    editor.SendScintilla(_Q.SCI_VERTICALCENTRECARET)

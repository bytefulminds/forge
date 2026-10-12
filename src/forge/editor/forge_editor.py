"""The Forge editor widget: a configured QsciScintilla."""

from __future__ import annotations

import re
import sys

from PyQt6.Qsci import QsciAPIs, QsciLexer, QsciScintilla
from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QToolTip

from forge.core.csvtext import detect_delimiter
from forge.core.eol import Eol
from forge.core.settings import EditorSettings
from forge.editor import decorations
from forge.editor.commenting import CommentMode, apply_comment
from forge.editor.csv_lexer import CsvLexer
from forge.editor.diagnostics import Diagnostic
from forge.editor.lexers import PLAIN_TEXT, Language, style_lexer
from forge.editor.search import HIGHLIGHT_INDICATOR
from forge.themes.theme import Theme

_EOL_MODES = {
    Eol.LF: QsciScintilla.EolMode.EolUnix,
    Eol.CRLF: QsciScintilla.EolMode.EolWindows,
    Eol.CR: QsciScintilla.EolMode.EolMac,
}

_LINE_NUMBER_MARGIN = 0
_FOLD_MARGIN = 2
DECORATION_DELAY_MS = 250
_FOLD_MARGIN_WIDTH = 14
_Q = QsciScintilla
# Arrow fold markers instead of the dated boxed tree.
_FOLD_MARKER_SHAPES = {
    _Q.SC_MARKNUM_FOLDEROPEN: _Q.SC_MARK_ARROWDOWN,
    _Q.SC_MARKNUM_FOLDEROPENMID: _Q.SC_MARK_ARROWDOWN,
    _Q.SC_MARKNUM_FOLDER: _Q.SC_MARK_ARROW,
    _Q.SC_MARKNUM_FOLDEREND: _Q.SC_MARK_ARROW,
    _Q.SC_MARKNUM_FOLDERSUB: _Q.SC_MARK_EMPTY,
    _Q.SC_MARKNUM_FOLDERTAIL: _Q.SC_MARK_EMPTY,
    _Q.SC_MARKNUM_FOLDERMIDTAIL: _Q.SC_MARK_EMPTY,
}


def _keyword_apis(lexer: QsciLexer) -> QsciAPIs | None:
    """Keywords of the language as completion words (QScintilla keyword sets 1 to 9)."""
    words: set[str] = set()
    for keyword_set in range(1, 10):
        keywords = lexer.keywords(keyword_set)
        if keywords:
            words.update(keywords.split())
    if not words:
        return None
    apis = QsciAPIs(lexer)
    for word in sorted(words):
        apis.add(word)
    apis.prepare()
    return apis


class ForgeEditor(QsciScintilla):
    def __init__(self, settings: EditorSettings, theme: Theme, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._settings = settings
        self._theme = theme
        self._language: Language = PLAIN_TEXT
        self._lexer: QsciLexer | None = None
        self._csv_delimiter: str | None = None
        self._keyword_apis: QsciAPIs | None = None
        self._large_file = False
        self._load_cancelled = False

        self.setUtf8(True)
        self.setAutoIndent(True)
        self.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.setCaretLineVisible(True)
        self.setCaretWidth(2)
        self.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle, _FOLD_MARGIN)
        for marker, shape in _FOLD_MARKER_SHAPES.items():
            self.SendScintilla(_Q.SCI_MARKERDEFINE, marker, shape)
        self.SendScintilla(_Q.SCI_SETFOLDFLAGS, _Q.SC_FOLDFLAG_LINEAFTER_CONTRACTED)
        self.setMarginWidth(_FOLD_MARGIN, _FOLD_MARGIN_WIDTH)
        self.setMarginType(_LINE_NUMBER_MARGIN, QsciScintilla.MarginType.NumberMargin)
        self.setMarginWidth(1, 0)
        self.SendScintilla(_Q.SCI_SETMARGINLEFT, 0, 8)
        # Roughly 1.5 line height for the code font.
        self.SendScintilla(_Q.SCI_SETEXTRAASCENT, 1)
        self.SendScintilla(_Q.SCI_SETEXTRADESCENT, 2)

        # Multi cursor (Ctrl/Cmd + click) and column selection (Alt + drag).
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPLESELECTION, 1)
        self.SendScintilla(QsciScintilla.SCI_SETADDITIONALSELECTIONTYPING, 1)
        self.SendScintilla(QsciScintilla.SCI_SETMULTIPASTE, 1)
        self.SendScintilla(QsciScintilla.SCI_SETVIRTUALSPACEOPTIONS, 1)

        # Horizontal scrollbar grows with the longest line instead of a fixed width.
        self.SendScintilla(QsciScintilla.SCI_SETSCROLLWIDTH, 1)
        self.SendScintilla(QsciScintilla.SCI_SETSCROLLWIDTHTRACKING, 1)

        if sys.platform == "darwin":
            # Scintilla binds Ctrl+L (Cmd+L on macOS) to "cut line"; on macOS
            # that key is Go to Line.
            self.SendScintilla(_Q.SCI_CLEARCMDKEY, ord("L") + (_Q.SCMOD_CTRL << 16))
        self.linesChanged.connect(self._update_line_number_width)

        self._diagnostic: Diagnostic | None = None
        self._diagnostic_range: tuple[int, int] | None = None
        self._decor_timer = QTimer(self)
        self._decor_timer.setSingleShot(True)
        self._decor_timer.setInterval(DECORATION_DELAY_MS)
        self._decor_timer.timeout.connect(self.refresh_decorations)
        self.textChanged.connect(self.schedule_decorations)
        self._brackets: list[tuple[int, int]] = []
        self._paint_timer = QTimer(self)
        self._paint_timer.setSingleShot(True)
        self._paint_timer.setInterval(40)
        self._paint_timer.timeout.connect(self.paint_decorations)
        self.SCN_UPDATEUI.connect(self._on_update_ui)
        self.SendScintilla(_Q.SCI_SETMOUSEDWELLTIME, 400)
        self.SCN_DWELLSTART.connect(self._on_dwell_start)
        self.SCN_DWELLEND.connect(lambda *_args: QToolTip.hideText())
        self.apply_settings(settings)

    # Configuration -------------------------------------------------------

    def font_for_settings(self) -> QFont:
        font = QFont(self._settings.font_family, self._settings.font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        # Ligatures make Scintilla misplace the caret.
        for feature in ("liga", "calt"):
            font.setFeature(QFont.Tag(feature), 0)
        return font

    def apply_settings(self, settings: EditorSettings) -> None:
        self._settings = settings
        self._apply_autocomplete()
        self.setTabWidth(settings.tab_width)
        self.setIndentationsUseTabs(not settings.use_spaces)
        self.setWrapMode(
            QsciScintilla.WrapMode.WrapWord
            if settings.word_wrap and not self._large_file
            else QsciScintilla.WrapMode.WrapNone
        )
        self.setWhitespaceVisibility(
            QsciScintilla.WhitespaceVisibility.WsVisible
            if settings.show_whitespace
            else QsciScintilla.WhitespaceVisibility.WsInvisible
        )
        self.setEolVisibility(settings.show_whitespace)
        self.setCaretLineVisible(settings.highlight_current_line)
        self.apply_theme(self._theme)

    def apply_theme(self, theme: Theme) -> None:
        self._theme = theme
        font = self.font_for_settings()
        margin_font = QFont(font)
        margin_font.setPointSize(max(6, font.pointSize() - 1))
        self.setFont(font)
        self.setMarginsFont(margin_font)
        self.setPaper(QColor(theme.editor_bg))
        self.setColor(QColor(theme.syntax.default))
        if self._lexer is not None:
            style_lexer(self._lexer, theme, font)
        # Margin and caret colors must be set after the lexer, which resets them.
        self.setMarginsBackgroundColor(QColor(theme.margin_bg))
        self.setMarginsForegroundColor(QColor(theme.margin_text))
        self.setFoldMarginColors(QColor(theme.margin_bg), QColor(theme.margin_bg))
        for marker in _FOLD_MARKER_SHAPES:
            # Fold markers are Scintilla owned, so the QsciScintilla helpers skip them.
            self.SendScintilla(_Q.SCI_MARKERSETFORE, marker, QColor(theme.margin_text))
            self.SendScintilla(_Q.SCI_MARKERSETBACK, marker, QColor(theme.margin_text))
        self.setCaretForegroundColor(QColor(theme.caret))
        self.setCaretLineBackgroundColor(QColor(theme.caret_line))
        self.setSelectionBackgroundColor(QColor(theme.selection))
        self.resetSelectionForegroundColor()
        self.setWhitespaceForegroundColor(QColor(theme.text_disabled))
        self.setIndentationGuidesForegroundColor(QColor(theme.indent_guide))
        # Search highlights (Find bar "highlight all").
        indicator = HIGHLIGHT_INDICATOR
        self.SendScintilla(_Q.SCI_INDICSETSTYLE, indicator, _Q.INDIC_ROUNDBOX)
        self.SendScintilla(_Q.SCI_INDICSETFORE, indicator, QColor(theme.accent))
        self.SendScintilla(_Q.SCI_INDICSETALPHA, indicator, 70)
        self.SendScintilla(_Q.SCI_INDICSETOUTLINEALPHA, indicator, 160)
        self.SendScintilla(_Q.SCI_INDICSETUNDER, indicator, 1)
        self._update_line_number_width()
        decorations.setup_indicators(self, theme)
        self.schedule_decorations()

    # Autocomplete --------------------------------------------------------

    def _apply_autocomplete(self) -> None:
        """Word completion like Notepad++: words from the document plus language keywords."""
        settings = self._settings
        if not settings.autocomplete:
            self.setAutoCompletionSource(_Q.AutoCompletionSource.AcsNone)
            return
        has_keywords = getattr(self, "_keyword_apis", None) is not None
        self.setAutoCompletionSource(
            _Q.AutoCompletionSource.AcsAll if has_keywords else _Q.AutoCompletionSource.AcsDocument
        )
        self.setAutoCompletionThreshold(max(1, settings.autocomplete_threshold))
        self.setAutoCompletionCaseSensitivity(False)
        self.setAutoCompletionReplaceWord(False)
        self.setAutoCompletionUseSingle(_Q.AutoCompletionUseSingle.AcusNever)

    def complete_word(self) -> None:
        """Show completions now (Ctrl+Space / Ctrl+Enter), even below the threshold."""
        self.autoCompleteFromAll()

    # Decorations ---------------------------------------------------------

    def schedule_decorations(self) -> None:
        self._decor_timer.start()

    def refresh_decorations(self) -> None:
        """Recompute bracket levels and repaint (debounced while typing)."""
        enabled = not self._large_file
        self._brackets = (
            decorations.compute_brackets(self, self._lexer)
            if enabled and self._settings.rainbow_brackets
            else []
        )
        self.paint_decorations()

    def paint_decorations(self) -> None:
        """Paint the visible part only; scrolling repaints (cheap)."""
        enabled = not self._large_file
        decorations.paint_window(
            self,
            self._brackets,
            self._settings.tab_width,
            enabled and self._settings.rainbow_brackets,
            enabled and self._settings.rainbow_indentation,
        )

    def _on_update_ui(self, updated: int) -> None:
        if updated & _Q.SC_UPDATE_V_SCROLL:
            self._paint_timer.start()

    @property
    def diagnostic(self) -> Diagnostic | None:
        return self._diagnostic

    def set_diagnostic(self, diagnostic: Diagnostic | None) -> None:
        """Underline ``diagnostic`` with a red squiggle (or clear it)."""
        length = int(self.SendScintilla(_Q.SCI_GETLENGTH))
        self.SendScintilla(_Q.SCI_SETINDICATORCURRENT, decorations.DIAGNOSTIC)
        self.SendScintilla(_Q.SCI_INDICATORCLEARRANGE, 0, length)
        self._diagnostic = diagnostic
        self._diagnostic_range = None
        if diagnostic is None or length == 0:
            return
        start, size = self._diagnostic_span(diagnostic)
        self._diagnostic_range = (start, start + size)
        self.SendScintilla(_Q.SCI_INDICATORFILLRANGE, start, size)

    def _diagnostic_span(self, diagnostic: Diagnostic) -> tuple[int, int]:
        """Byte range to underline: the token at the error, at least one character."""
        line = max(0, min(diagnostic.line - 1, self.lines() - 1))
        text = str(self.text(line)).rstrip("\r\n")
        while not text.strip() and line > 0:  # error after the end: mark the last text
            line -= 1
            text = str(self.text(line)).rstrip("\r\n")
        column = max(0, min(diagnostic.column - 1, max(0, len(text) - 1)))
        token = re.match(r"\S+", text[column:])
        size_chars = len(token.group(0)) if token else 1
        line_start = int(self.SendScintilla(_Q.SCI_POSITIONFROMLINE, line))
        start = line_start + len(text[:column].encode("utf-8"))
        size = max(1, len(text[column : column + size_chars].encode("utf-8")))
        return start, size

    def _on_dwell_start(self, position: int, x: int, y: int) -> None:
        span = self._diagnostic_range
        if self._diagnostic is None or span is None or position < 0:
            return
        if span[0] <= position <= span[1]:
            QToolTip.showText(self.mapToGlobal(QPoint(x, y + 12)), self._diagnostic.message, self)

    # Language ------------------------------------------------------------

    @property
    def language(self) -> Language:
        return self._language

    def set_language(self, language: Language) -> None:
        self._language = language
        # Large files keep their language name but skip the lexer: styling
        # hundreds of megabytes is what makes editors freeze.
        use_lexer = language.lexer is not None and not self._large_file
        self._lexer = language.lexer(self) if use_lexer and language.lexer else None
        if isinstance(self._lexer, CsvLexer) and self._csv_delimiter:
            self._lexer.set_delimiter(self._csv_delimiter)
        self.setLexer(self._lexer)
        self._keyword_apis = None
        if self._lexer is not None:
            self._keyword_apis = _keyword_apis(self._lexer)
        self._apply_autocomplete()
        self.apply_theme(self._theme)
        self.schedule_decorations()

    # CSV -------------------------------------------------------------------

    @property
    def csv_delimiter(self) -> str:
        """The delimiter in use: chosen by the user, or detected from the text."""
        if isinstance(self._lexer, CsvLexer):
            return self._lexer.delimiter
        if self._csv_delimiter:
            return self._csv_delimiter
        length = min(int(self.SendScintilla(self.SCI_GETLENGTH)), 20_000)
        sample = bytes(self.bytes(0, length).data())[:length].decode("utf-8", "replace")
        return detect_delimiter(sample)

    @property
    def csv_delimiter_choice(self) -> str | None:
        """The delimiter the user chose, or ``None`` for automatic detection."""
        return self._csv_delimiter

    def set_csv_delimiter(self, delimiter: str | None) -> None:
        self._csv_delimiter = delimiter or None
        if isinstance(self._lexer, CsvLexer):
            self._lexer.set_delimiter(self._csv_delimiter)

    # Large files ---------------------------------------------------------

    @property
    def large_file(self) -> bool:
        return self._large_file

    def set_large_file_mode(self, enabled: bool) -> None:
        """Turn off syntax highlighting, word wrap and folding for very large files."""
        self._large_file = enabled
        style = _Q.FoldStyle.NoFoldStyle if enabled else _Q.FoldStyle.BoxedTreeFoldStyle
        self.setFolding(style, _FOLD_MARGIN)
        if not enabled:
            for marker, shape in _FOLD_MARKER_SHAPES.items():
                self.SendScintilla(_Q.SCI_MARKERDEFINE, marker, shape)
            self.setMarginWidth(_FOLD_MARGIN, _FOLD_MARGIN_WIDTH)
        self.apply_settings(self._settings)
        self.set_language(self._language)

    def load_utf8(self, utf8: bytes) -> None:
        """Replace the text with UTF-8 bytes in one call, without an undo step.

        The bytes go straight to Scintilla, which stores UTF-8 itself, so no
        Python string is created. One call is much faster than several: every
        Scintilla insert costs time proportional to the document size.
        """
        self.SendScintilla(_Q.SCI_SETUNDOCOLLECTION, 0)
        self.clear()
        self.SendScintilla(_Q.SCI_APPENDTEXT, len(utf8), utf8)
        self.SendScintilla(_Q.SCI_SETUNDOCOLLECTION, 1)
        self.SendScintilla(_Q.SCI_EMPTYUNDOBUFFER)
        self.setModified(False)
        self.setCursorPosition(0, 0)

    def cancel_loading(self) -> None:
        """Mark a background load for this editor as no longer wanted."""
        self._load_cancelled = True

    @property
    def load_cancelled(self) -> bool:
        return self._load_cancelled

    # Comments ------------------------------------------------------------

    def comment_lines(self, mode: CommentMode) -> bool:
        """Comment, uncomment or toggle the lines touched by the main selection.

        Returns False when the language has no comment syntax.
        """
        style = self._language.comment
        if not style.supported:
            return False
        sel_start = self.SendScintilla(_Q.SCI_GETSELECTIONSTART)
        sel_end = self.SendScintilla(_Q.SCI_GETSELECTIONEND)
        first = self.SendScintilla(_Q.SCI_LINEFROMPOSITION, sel_start)
        last = self.SendScintilla(_Q.SCI_LINEFROMPOSITION, sel_end)
        # A selection ending at the start of a line does not include that line.
        if last > first and sel_end == self.SendScintilla(_Q.SCI_POSITIONFROMLINE, last):
            last -= 1
        start = self.SendScintilla(_Q.SCI_POSITIONFROMLINE, first)
        end = self.SendScintilla(_Q.SCI_GETLINEENDPOSITION, last)

        self.SendScintilla(_Q.SCI_SETSEL, start, end)
        parts = re.split(r"(\r\n|\n|\r)", self.selectedText())
        lines, separators = parts[0::2], parts[1::2]
        changed = apply_comment(lines, style, mode)
        new_text = "".join(
            line + (separators[i] if i < len(separators) else "") for i, line in enumerate(changed)
        )
        self.beginUndoAction()
        try:
            self.replaceSelectedText(new_text)
        finally:
            self.endUndoAction()
        self.SendScintilla(_Q.SCI_SETSEL, start, start + len(new_text.encode("utf-8")))
        return True

    # Line endings --------------------------------------------------------

    def set_eol(self, eol: Eol) -> None:
        self.setEolMode(_EOL_MODES[eol])

    def convert_eols(self, eol: Eol) -> None:
        """Rewrite every line ending in the document (one undo step)."""
        self.beginUndoAction()
        try:
            self.convertEols(_EOL_MODES[eol])
        finally:
            self.endUndoAction()
        self.set_eol(eol)

    # Internals -----------------------------------------------------------

    def _update_line_number_width(self) -> None:
        if not self._settings.show_line_numbers:
            self.setMarginWidth(_LINE_NUMBER_MARGIN, 0)
            return
        digits = max(3, len(str(self.lines())))
        self.setMarginWidth(_LINE_NUMBER_MARGIN, "9" * (digits + 1))

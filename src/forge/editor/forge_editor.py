"""The Forge editor widget: a configured QsciScintilla."""

from __future__ import annotations

import re

from PyQt6.Qsci import QsciLexer, QsciScintilla
from PyQt6.QtGui import QColor, QFont

from forge.core.eol import Eol
from forge.core.settings import EditorSettings
from forge.editor.commenting import CommentMode, apply_comment
from forge.editor.lexers import PLAIN_TEXT, Language, style_lexer
from forge.themes.theme import Theme

_EOL_MODES = {
    Eol.LF: QsciScintilla.EolMode.EolUnix,
    Eol.CRLF: QsciScintilla.EolMode.EolWindows,
    Eol.CR: QsciScintilla.EolMode.EolMac,
}

_LINE_NUMBER_MARGIN = 0
_FOLD_MARGIN = 2
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


class ForgeEditor(QsciScintilla):
    def __init__(self, settings: EditorSettings, theme: Theme, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._settings = settings
        self._theme = theme
        self._language: Language = PLAIN_TEXT
        self._lexer: QsciLexer | None = None

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

        self.linesChanged.connect(self._update_line_number_width)
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
        self.setTabWidth(settings.tab_width)
        self.setIndentationsUseTabs(not settings.use_spaces)
        self.setWrapMode(
            QsciScintilla.WrapMode.WrapWord
            if settings.word_wrap
            else QsciScintilla.WrapMode.WrapNone
        )
        self.setWhitespaceVisibility(
            QsciScintilla.WhitespaceVisibility.WsVisible
            if settings.show_whitespace
            else QsciScintilla.WhitespaceVisibility.WsInvisible
        )
        self.setEolVisibility(settings.show_whitespace)
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
        self.setMatchedBraceBackgroundColor(QColor(theme.brace_match_bg))
        self.setMatchedBraceForegroundColor(QColor(theme.text))
        self.setUnmatchedBraceForegroundColor(QColor(theme.error))
        self.setWhitespaceForegroundColor(QColor(theme.text_disabled))
        self.setIndentationGuidesForegroundColor(QColor(theme.indent_guide))
        self._update_line_number_width()

    # Language ------------------------------------------------------------

    @property
    def language(self) -> Language:
        return self._language

    def set_language(self, language: Language) -> None:
        self._language = language
        self._lexer = language.lexer(self) if language.lexer is not None else None
        self.setLexer(self._lexer)
        self.apply_theme(self._theme)

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

    # Internals -----------------------------------------------------------

    def _update_line_number_width(self) -> None:
        if not self._settings.show_line_numbers:
            self.setMarginWidth(_LINE_NUMBER_MARGIN, 0)
            return
        digits = max(3, len(str(self.lines())))
        self.setMarginWidth(_LINE_NUMBER_MARGIN, "9" * (digits + 1))

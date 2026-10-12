"""The Forge editor widget: a configured QsciScintilla."""

from __future__ import annotations

from PyQt6.Qsci import QsciLexer, QsciScintilla
from PyQt6.QtGui import QColor, QFont

from forge.core.eol import Eol
from forge.core.settings import EditorSettings
from forge.editor.lexers import PLAIN_TEXT, Language, style_lexer
from forge.themes.theme import Theme

_EOL_MODES = {
    Eol.LF: QsciScintilla.EolMode.EolUnix,
    Eol.CRLF: QsciScintilla.EolMode.EolWindows,
    Eol.CR: QsciScintilla.EolMode.EolMac,
}

_LINE_NUMBER_MARGIN = 0
_FOLD_MARGIN = 2
_FOLD_MARKERS = range(25, 32)  # Scintilla SC_MARKNUM_FOLDEREND .. SC_MARKNUM_FOLDEROPEN


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
        self.setMarginType(_LINE_NUMBER_MARGIN, QsciScintilla.MarginType.NumberMargin)
        self.setMarginWidth(1, 0)

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
        self.setFont(font)
        self.setMarginsFont(font)
        self.setPaper(QColor(theme.background))
        self.setColor(QColor(theme.syntax.default))
        if self._lexer is not None:
            style_lexer(self._lexer, theme, font)
        # Margin and caret colors must be set after the lexer, which resets them.
        self.setMarginsBackgroundColor(QColor(theme.margin_background))
        self.setMarginsForegroundColor(QColor(theme.margin_text))
        self.setFoldMarginColors(QColor(theme.margin_background), QColor(theme.margin_background))
        for marker in _FOLD_MARKERS:
            # Fold markers are Scintilla owned, so the QsciScintilla helpers skip them.
            self.SendScintilla(
                QsciScintilla.SCI_MARKERSETFORE, marker, QColor(theme.margin_background)
            )
            self.SendScintilla(QsciScintilla.SCI_MARKERSETBACK, marker, QColor(theme.margin_text))
        self.setCaretForegroundColor(QColor(theme.caret))
        self.setCaretLineBackgroundColor(QColor(theme.caret_line))
        self.setSelectionBackgroundColor(QColor(theme.selection))
        self.resetSelectionForegroundColor()
        self.setMatchedBraceBackgroundColor(QColor(theme.selection))
        self.setMatchedBraceForegroundColor(QColor(theme.focus))
        self.setUnmatchedBraceForegroundColor(QColor(theme.error))
        self.setWhitespaceForegroundColor(QColor(theme.text_muted))
        self.setIndentationGuidesForegroundColor(QColor(theme.border))
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

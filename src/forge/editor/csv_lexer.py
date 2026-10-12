"""CSV / TSV highlighting: every column gets its own color ("rainbow CSV")."""

from __future__ import annotations

from PyQt6.Qsci import QsciLexerCustom, QsciScintilla
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QColor, QFont

from forge.core.csvtext import detect_delimiter

COLUMN_STYLES = 8
DELIMITER_STYLE = COLUMN_STYLES  # style number for the delimiters themselves


class CsvLexer(QsciLexerCustom):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._delimiter: int | None = None
        self._forced = False

    def language(self) -> str:
        return "CSV"

    def description(self, style: int) -> str:
        if style < COLUMN_STYLES:
            return f"Column {style + 1}"
        if style == DELIMITER_STYLE:
            return "Delimiter"
        return ""

    @property
    def delimiter(self) -> str:
        editor = self.editor()
        if self._delimiter is None:
            return chr(self._detect(editor)) if editor is not None else ","
        return chr(self._delimiter)

    @property
    def is_automatic(self) -> bool:
        return not self._forced

    def set_delimiter(self, delimiter: str | None) -> None:
        """Use ``delimiter``, or detect it again from the text when ``None``."""
        self._forced = delimiter is not None
        self._delimiter = ord(delimiter) if delimiter else None
        editor = self.editor()
        if editor is not None:
            editor.SendScintilla(QsciScintilla.SCI_COLOURISE, 0, -1)

    def apply_palette(self, colors: tuple[str, ...], delimiter_color: str, font: QFont) -> None:
        for style in range(COLUMN_STYLES):
            self.setColor(QColor(colors[style % len(colors)]), style)
            self.setFont(font, style)
        self.setColor(QColor(delimiter_color), DELIMITER_STYLE)
        self.setFont(font, DELIMITER_STYLE)

    def _detect(self, editor: QsciScintilla) -> int:
        if self._delimiter is None:
            length = min(int(editor.SendScintilla(QsciScintilla.SCI_GETLENGTH)), 20_000)
            raw = bytes(editor.bytes(0, length).data())[:length]
            sample = raw.decode("utf-8", errors="replace")
            detected = ord(detect_delimiter(sample))
            # Decide for good only once there is a full line to look at; the
            # lexer is created before a file's text is loaded.
            if "\n" not in sample and "\r" not in sample:
                return detected
            self._delimiter = detected
        return self._delimiter

    def styleText(self, start: int, end: int) -> None:
        editor = self.editor()
        if editor is None:
            return
        delimiter = self._detect(editor)
        # Always restyle whole lines so the column count starts at zero.
        first_line = int(editor.SendScintilla(QsciScintilla.SCI_LINEFROMPOSITION, start))
        start = int(editor.SendScintilla(QsciScintilla.SCI_POSITIONFROMLINE, first_line))
        # QsciScintilla.bytes() appends a terminating NUL: cut to the range.
        data = bytes(editor.bytes(start, end).data())[: end - start]
        self.startStyling(start)
        column = 0
        quoted = False
        run_style = 0
        run_length = 0
        quote, newline, carriage = ord('"'), ord("\n"), ord("\r")
        for byte in data:
            if byte == quote:
                quoted = not quoted
                style = column % COLUMN_STYLES
            elif (byte == delimiter and not quoted) or (byte in (newline, carriage) and not quoted):
                style = DELIMITER_STYLE
            else:
                style = column % COLUMN_STYLES
            if style != run_style and run_length:
                self.setStyling(run_length, run_style)
                run_length = 0
            run_style = style
            run_length += 1
            if byte == delimiter and not quoted:
                column += 1
            elif byte == newline and not quoted:
                column = 0
        if run_length:
            self.setStyling(run_length, run_style)

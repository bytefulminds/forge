"""Code Shot: the selected code as a tidy image, with the editor's syntax
colors, in a window frame on an optional colored backdrop. Copy it to paste
in a manual, chat or mail, or save it as PNG."""

from __future__ import annotations

from dataclasses import dataclass, replace

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import EditorHandle, ForgeAPI, tr
from forge.themes import tokens
from forge.themes.theme import Theme
from forge.themes.tokens import mix

_Q = QsciScintilla
MAX_LINES = 400
FONT_PX = 14
SCALE = 2  # render at twice the size: sharp on high resolution screens and in documents

# A run of text in one color: (text, color, bold, italic).
Run = tuple[str, QColor, bool, bool]


@dataclass(frozen=True)
class Options:
    title: str = ""
    line_numbers: bool = True
    first_number: int = 1
    frame: bool = True  # window frame with the three dots
    backdrop: str = "forge"  # key in backdrops(), "none" for transparent


def backdrops() -> dict[str, tuple[str, str] | None]:
    """Backdrop gradients (top left to bottom right) by key."""
    return {
        "forge": (tokens.NIGHT_BLUE, tokens.SKY_BLUE),
        "fresh": (tokens.CYAN, tokens.LIME),
        "sunset": (tokens.WARNING, tokens.ERROR),
        "graphite": (tokens.GRAPHITE, mix(tokens.GRAPHITE, tokens.LIGHT, 0.25)),
        "none": None,
    }


def backdrop_names() -> dict[str, str]:
    return {
        "forge": tr("Forge blue"),
        "fresh": tr("Fresh"),
        "sunset": tr("Sunset"),
        "graphite": tr("Graphite"),
        "none": tr("None (transparent)"),
    }


# Collecting styled text ------------------------------------------------------------


def collect(editor: QsciScintilla, first: int, last: int, theme: Theme) -> list[list[Run]]:
    """Lines ``first`` to ``last`` (0-based) as colored runs, using the
    lexer's colors. Common leading indentation is removed; tabs become spaces."""
    send = editor.SendScintilla
    send(_Q.SCI_COLOURISE, 0, -1)
    lexer = editor.lexer()
    tab_width = max(1, int(editor.tabWidth()))
    default = QColor(theme.text)
    lines: list[list[Run]] = []
    for line in range(first, last + 1):
        text = str(editor.text(line)).rstrip("\r\n")
        position = int(send(_Q.SCI_POSITIONFROMLINE, line))
        runs: list[Run] = []
        column = 0
        for char in text:
            style = int(send(_Q.SCI_GETSTYLEAT, position))
            position += len(char.encode("utf-8"))
            if char == "\t":
                spaces = tab_width - column % tab_width
                char = " " * spaces
            column += len(char)
            if lexer is not None:
                color = lexer.color(style)
                font = lexer.font(style)
                bold, italic = font.bold(), font.italic()
            else:
                color, bold, italic = default, False, False
            if runs and runs[-1][1] == color and runs[-1][2:] == (bold, italic):
                runs[-1] = (runs[-1][0] + char, color, bold, italic)
            else:
                runs.append((char, QColor(color), bold, italic))
        lines.append(runs)
    return _dedent(lines)


def _dedent(lines: list[list[Run]]) -> list[list[Run]]:
    """Remove the indentation all non-empty lines share."""

    def indent(runs: list[Run]) -> int | None:
        text = "".join(run[0] for run in runs)
        return None if not text.strip() else len(text) - len(text.lstrip(" "))

    cut = min((w for w in map(indent, lines) if w is not None), default=0)
    if cut == 0:
        return lines
    result: list[list[Run]] = []
    for runs in lines:
        remaining = cut
        trimmed: list[Run] = []
        for text, color, bold, italic in runs:
            if remaining:
                take = min(remaining, len(text))
                text, remaining = text[take:], remaining - take
            if text:
                trimmed.append((text, color, bold, italic))
        result.append(trimmed)
    return result


def trim_blank(lines: list[list[Run]]) -> tuple[list[list[Run]], int]:
    """Drop blank lines at the start and end; also returns how many went from the start."""
    start = 0
    while start < len(lines) and not "".join(r[0] for r in lines[start]).strip():
        start += 1
    end = len(lines)
    while end > start and not "".join(r[0] for r in lines[end - 1]).strip():
        end -= 1
    return lines[start:end], start


# Rendering -------------------------------------------------------------------------


def code_font(bold: bool = False, italic: bool = False) -> QFont:
    font = QFont("JetBrains Mono")
    font.setPixelSize(FONT_PX)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setBold(bold)
    font.setItalic(italic)
    for feature in ("liga", "calt"):  # show "->" as typed, not as an arrow
        font.setFeature(QFont.Tag(feature), 0)
    return font


def render(lines: list[list[Run]], theme: Theme, options: Options) -> QImage:
    font = code_font()
    metrics = QFontMetricsF(font)
    line_height = round(metrics.height() * 1.35)
    char_width = metrics.horizontalAdvance("M")
    longest = max((sum(len(run[0]) for run in runs) for runs in lines), default=0)
    last_number = options.first_number + max(0, len(lines) - 1)
    gutter = (len(str(last_number)) + 2) * char_width if options.line_numbers else 0
    pad_x, pad_y = 22.0, 18.0
    bar = 38.0 if options.frame else 0.0
    window_w = max(280.0, pad_x * 2 + gutter + longest * char_width)
    window_h = bar + pad_y * 2 + max(1, len(lines)) * line_height
    backdrop = backdrops().get(options.backdrop)
    margin = 48.0 if backdrop else 0.0
    width, height = window_w + margin * 2, window_h + margin * 2

    image = QImage(
        round(width * SCALE), round(height * SCALE), QImage.Format.Format_ARGB32_Premultiplied
    )
    image.fill(Qt.GlobalColor.transparent)
    image.setDevicePixelRatio(SCALE)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    if backdrop:
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0, QColor(backdrop[0]))
        gradient.setColorAt(1, QColor(backdrop[1]))
        painter.fillRect(QRectF(0, 0, width, height), gradient)

    window = QRectF(margin, margin, window_w, window_h)
    radius = 10.0 if (options.frame or backdrop) else 0.0
    if backdrop:  # soft shadow under the window
        for step in range(12, 0, -1):
            shadow = QColor(0, 0, 0, 7)
            path = QPainterPath()
            grow = step * 1.6
            path.addRoundedRect(
                window.adjusted(-grow, -grow + 10, grow, grow + 10), radius + grow, radius + grow
            )
            painter.fillPath(path, shadow)
    path = QPainterPath()
    path.addRoundedRect(window, radius, radius)
    painter.fillPath(path, QColor(theme.editor_bg))
    painter.setClipPath(path)

    if options.frame:
        painter.fillRect(QRectF(window.x(), window.y(), window_w, bar), QColor(theme.chrome_bg))
        painter.fillRect(
            QRectF(window.x(), window.y() + bar - 1, window_w, 1), QColor(theme.border)
        )
        for index, color in enumerate((tokens.MAC_CLOSE, tokens.MAC_MINIMIZE, tokens.MAC_ZOOM)):
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(window.x() + 20 + index * 20, window.y() + bar / 2), 6, 6)
        if options.title:
            title_font = QFont(font)
            title_font.setPixelSize(13)
            painter.setFont(title_font)
            painter.setPen(QColor(theme.text_muted))
            painter.drawText(
                QRectF(window.x() + 80, window.y(), window_w - 160, bar),
                Qt.AlignmentFlag.AlignCenter,
                options.title,
            )

    top = window.y() + bar + pad_y
    baseline_shift = (line_height - metrics.height()) / 2 + metrics.ascent()
    for index, runs in enumerate(lines):
        y = top + index * line_height + baseline_shift
        x = window.x() + pad_x
        if options.line_numbers:
            painter.setFont(font)
            painter.setPen(QColor(theme.margin_text))
            number = str(options.first_number + index)
            painter.drawText(QPointF(x + gutter - (len(number) + 2) * char_width, y), number)
            x += gutter
        for text, run_color, bold, italic in runs:
            painter.setFont(code_font(bold, italic))
            painter.setPen(run_color)
            painter.drawText(QPointF(x, y), text)
            x += len(text) * char_width
    painter.end()
    return image


# The window ------------------------------------------------------------------------


class ImageView(QWidget):
    """Shows an image scaled down to fit (never up), centered."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image = QImage()
        self.setMinimumSize(320, 200)

    def set_image(self, image: QImage) -> None:
        self.image = image
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        if self.image.isNull():
            return
        size = self.image.deviceIndependentSize()
        scale = min(1.0, self.width() / size.width(), self.height() / size.height())
        w, h = size.width() * scale, size.height() * scale
        target = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, self.image)
        painter.end()


class CodeShot:
    def __init__(self, api: ForgeAPI, lines: list[list[Run]], options: Options) -> None:
        self.api = api
        self.lines = lines
        self.options = options
        self.image = QImage()
        self.dialog = api.framed_dialog(tr("Code Shot"), resizable=True)
        self.dialog.setProperty("forgeTool", self)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel(tr("Title"), body))
        self.title = QLineEdit(options.title, body)
        self.title.setPlaceholderText(tr("File name or caption"))
        row.addWidget(self.title, 1)
        row.addWidget(QLabel(tr("Backdrop"), body))
        self.backdrop = QComboBox(body)
        for key, name in backdrop_names().items():
            self.backdrop.addItem(name, key)
        self.backdrop.setCurrentIndex(max(0, self.backdrop.findData(options.backdrop)))
        row.addWidget(self.backdrop)
        self.numbers = QCheckBox(tr("Line numbers"), body)
        self.numbers.setChecked(options.line_numbers)
        row.addWidget(self.numbers)
        self.frame = QCheckBox(tr("Window frame"), body)
        self.frame.setChecked(options.frame)
        row.addWidget(self.frame)
        layout.addLayout(row)

        self.preview = ImageView(body)
        layout.addWidget(self.preview, 1)
        self.size_note = QLabel(body)
        self.size_note.setObjectName("resultNote")
        layout.addWidget(self.size_note)

        buttons = QDialogButtonBox(body)
        save = QPushButton(tr("Save PNG..."), body)
        save.clicked.connect(self.save)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.ActionRole)
        copy = QPushButton(tr("Copy Image"), body)
        copy.setDefault(True)
        copy.clicked.connect(self.copy)
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.AcceptRole)
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        assert close is not None
        close.clicked.connect(self.dialog.reject)
        layout.addWidget(buttons)

        self.title.textChanged.connect(lambda _t: self.update())
        self.backdrop.currentIndexChanged.connect(lambda _i: self.update())
        self.numbers.toggled.connect(lambda _on: self.update())
        self.frame.toggled.connect(lambda _on: self.update())
        self.update()
        hint = self.image.deviceIndependentSize()
        self.dialog.resize(
            max(720, min(1100, round(hint.width()) + 60)),
            max(420, min(820, round(hint.height()) + 200)),
        )

    def current_options(self) -> Options:
        return replace(
            self.options,
            title=self.title.text().strip(),
            backdrop=str(self.backdrop.currentData()),
            line_numbers=self.numbers.isChecked(),
            frame=self.frame.isChecked(),
        )

    def update(self) -> None:
        self.image = render(self.lines, self.api.theme, self.current_options())
        self.preview.set_image(self.image)
        self.size_note.setText(
            tr("{width} x {height} pixels", width=self.image.width(), height=self.image.height())
        )

    def copy(self) -> None:
        self.api.copy_image(self.image)
        self.api.status(tr("Code image copied. Paste it where you like."))
        self.dialog.accept()

    def save(self) -> None:
        name = (self.title.text().strip() or "code").rsplit(".", 1)[0] + ".png"
        path = self.api.choose_save_file(tr("Save Code Shot"), name, [tr("PNG image (*.png)")])
        if path is None:
            return
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png")
        if self.image.save(str(path), "PNG"):
            self.api.status(tr("Saved {name}.", name=path.name))
            self.dialog.accept()
        else:
            self.api.notify(tr("Could not save {name}.", name=path.name), "error")

    def exec(self) -> int:
        return self.dialog.exec()


def open_code_shot(api: ForgeAPI, editor: EditorHandle) -> CodeShot | None:
    if not editor.has_selection():
        api.notify(tr("Select the code for the code shot first."), "info")
        return None
    first, last = editor.selected_line_range()
    if last - first + 1 > MAX_LINES:
        api.notify(tr("Select at most {count} lines for a code shot.", count=MAX_LINES), "warning")
        return None
    lines, skipped = trim_blank(collect(editor.widget, first, last, api.theme))
    if not lines:
        api.status(tr("Nothing to show: the selection is empty."))
        return None
    title = editor.path.name if editor.path is not None else ""
    shot = CodeShot(api, lines, Options(title=title, first_number=first + skipped + 1))
    shot.exec()
    return shot

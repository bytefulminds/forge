"""Regex tester: a pattern, test text with live highlighted matches, the groups
of every match and a replace preview. Uses Python's re, like Find in Files."""

from __future__ import annotations

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI, tr
from forge.tools.utilities import regex_core as core

_Q = QsciScintilla
MATCH_INDICATOR = 24
# Groups get a thick underline, one color per group number (cycling).
GROUP_INDICATORS = (25, 26, 27, 28)
DELAY_MS = 150
MAX_TEXT = 200_000

SAMPLE = (
    "Order 1042 shipped to mark@example.com on 2026-11-15.\n"
    "Order 1043 shipped to info@bytefulminds.nl on 2026-11-16.\n"
    "Call +31 6 1234 5678 for questions.\n"
)
SAMPLE_PATTERN = r"(?P<user>[\w.+-]+)@(?P<domain>[\w-]+\.[\w.]+)"


def _flag_tips() -> dict[str, str]:
    return {
        "i": tr("Ignore case"),
        "m": tr("Multiline: ^ and $ match at every line"),
        "s": tr("Dot matches newlines too"),
        "x": tr("Verbose: spaces and # comments in the pattern are ignored"),
    }


def _mono() -> QFont:
    font = QFont("JetBrains Mono", 10)
    font.setStyleHint(QFont.StyleHint.Monospace)
    for feature in ("liga", "calt"):
        font.setFeature(QFont.Tag(feature), 0)
    return font


class RegexTester:
    def __init__(self, api: ForgeAPI, text: str, pattern: str = "") -> None:
        self.api = api
        self.result = core.Result()
        self.dialog = api.framed_dialog(tr("Regex Tester"), resizable=True)
        self.dialog.setModal(False)
        self.dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.dialog.setProperty("forgeTool", self)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Pattern and flags.
        row = QHBoxLayout()
        row.setSpacing(4)
        self.pattern = QLineEdit(pattern, body)
        self.pattern.setObjectName("monoField")
        self.pattern.setPlaceholderText(tr("Regular expression"))
        row.addWidget(self.pattern, 1)
        self.flags: dict[str, QToolButton] = {}
        for letter, tip in _flag_tips().items():
            button = QToolButton(body)
            button.setObjectName("findOption")
            button.setText(letter)
            button.setCheckable(True)
            button.setToolTip(tip)
            button.toggled.connect(lambda _on: self.schedule())
            self.flags[letter] = button
            row.addWidget(button)
        layout.addLayout(row)
        self.summary = QLabel(body)
        self.summary.setObjectName("resultNote")
        layout.addWidget(self.summary)

        # Test text above, matches below.
        self.text = api.create_viewer()
        self.text.setReadOnly(False)
        self.text.setParent(body)
        self.text.setText(text)
        self.text.setWrapMode(_Q.WrapMode.WrapWord)
        self._setup_indicators()
        self.matches = QTreeWidget(body)
        self.matches.setObjectName("regexMatches")
        self.matches.setHeaderLabels([tr("Match"), tr("Position"), tr("Text")])
        self.matches.setRootIsDecorated(True)
        self.matches.setUniformRowHeights(True)
        self.matches.setColumnWidth(0, 120)
        self.matches.setColumnWidth(1, 90)
        self.matches.currentItemChanged.connect(self._picked)
        splitter = QSplitter(Qt.Orientation.Vertical, body)
        splitter.addWidget(self._titled(tr("Test text"), self.text, body))
        splitter.addWidget(self._titled(tr("Matches and groups"), self.matches, body))
        splitter.setSizes([220, 220])
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        # Replace preview.
        replace_row = QHBoxLayout()
        self.replacement = QLineEdit(body)
        self.replacement.setObjectName("monoField")
        self.replacement.setPlaceholderText(tr("Replace with (\\1 or \\g<name> for groups)"))
        replace_row.addWidget(self.replacement, 1)
        layout.addLayout(replace_row)
        self.replaced = api.create_viewer()
        self.replaced.setParent(body)
        self.replaced.setWrapMode(_Q.WrapMode.WrapWord)
        self.replaced.setMinimumHeight(70)
        self.replaced.setMaximumHeight(110)
        self.replaced.hide()
        layout.addWidget(self.replaced)

        buttons = QDialogButtonBox(body)
        copy_python = QPushButton(tr("Copy as Python"), body)
        copy_python.clicked.connect(self.copy_python)
        buttons.addButton(copy_python, QDialogButtonBox.ButtonRole.ActionRole)
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        assert close is not None
        close.clicked.connect(self.dialog.close)
        layout.addWidget(buttons)

        self.timer = QTimer(self.dialog)
        self.timer.setSingleShot(True)
        self.timer.setInterval(DELAY_MS)
        self.timer.timeout.connect(self.run)
        self.pattern.textChanged.connect(lambda _t: self.schedule())
        self.replacement.textChanged.connect(lambda _t: self.schedule())
        self.text.textChanged.connect(self.schedule)
        self.dialog.resize(780, 640)
        self.run()

    @staticmethod
    def _titled(title: str, widget: QWidget, parent: QWidget) -> QWidget:
        box = QWidget(parent)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        label = QLabel(title, box)
        label.setObjectName("paneTitle")
        layout.addWidget(label)
        layout.addWidget(widget, 1)
        return box

    def group_colors(self) -> tuple[str, ...]:
        theme = self.api.theme
        colors = theme.rainbow or (theme.success, theme.warning, theme.error, theme.accent)
        return tuple(colors[i % len(colors)] for i in range(len(GROUP_INDICATORS)))

    def _setup_indicators(self) -> None:
        theme = self.api.theme
        send = self.text.SendScintilla
        send(_Q.SCI_INDICSETSTYLE, MATCH_INDICATOR, _Q.INDIC_ROUNDBOX)
        send(_Q.SCI_INDICSETFORE, MATCH_INDICATOR, QColor(theme.accent))
        send(_Q.SCI_INDICSETALPHA, MATCH_INDICATOR, 70)
        send(_Q.SCI_INDICSETOUTLINEALPHA, MATCH_INDICATOR, 220)
        send(_Q.SCI_INDICSETUNDER, MATCH_INDICATOR, 1)
        for indicator, color in zip(GROUP_INDICATORS, self.group_colors(), strict=True):
            send(_Q.SCI_INDICSETSTYLE, indicator, _Q.INDIC_COMPOSITIONTHICK)
            send(_Q.SCI_INDICSETFORE, indicator, QColor(color))
            send(_Q.SCI_INDICSETUNDER, indicator, 1)

    def schedule(self) -> None:
        self.timer.start()

    def flag_value(self) -> int:
        return core.flag_value(letter for letter, b in self.flags.items() if b.isChecked())

    def run(self) -> None:
        self.timer.stop()
        pattern = self.pattern.text()
        text = str(self.text.text())
        flags = self.flag_value()
        self.result = core.evaluate(pattern, flags, text)
        self.pattern.setProperty("invalid", bool(self.result.error))
        _repolish(self.pattern)
        self._highlight(text)
        self._fill_matches()
        if self.result.error:
            self.summary.setObjectName("toolError")
            position = self.result.error_position
            self.summary.setText(
                tr("{error} (at position {position})", error=self.result.error, position=position)
                if position is not None
                else self.result.error
            )
        else:
            self.summary.setObjectName("resultNote")
            count = len(self.result.matches)
            groups = len(self.result.matches[0].groups) if self.result.matches else 0
            if not pattern:
                message = tr("Type a pattern to see its matches.")
            elif count == 0:
                message = tr("No matches.")
            else:
                message = tr("{count} matches", count=count) if count != 1 else tr("1 match")
                if groups:
                    message += ", " + tr("{count} groups each", count=groups)
                if self.result.truncated:
                    message += " " + tr("(stopped at {limit})", limit=core.MAX_MATCHES)
            self.summary.setText(message)
        _repolish(self.summary)
        self._update_replace(pattern, flags, text)

    def _highlight(self, text: str) -> None:
        send = self.text.SendScintilla
        length = int(send(_Q.SCI_GETLENGTH))
        for indicator in (MATCH_INDICATOR, *GROUP_INDICATORS):
            send(_Q.SCI_SETINDICATORCURRENT, indicator)
            send(_Q.SCI_INDICATORCLEARRANGE, 0, length)
        if not self.result.matches:
            return
        offsets: list[int] = []
        for match in self.result.matches:
            offsets += [match.start, match.end]
            for group in match.groups:
                if group.start >= 0:
                    offsets += [group.start, group.end]
        positions = core.byte_offsets(text, offsets)
        send(_Q.SCI_SETINDICATORCURRENT, MATCH_INDICATOR)
        for match in self.result.matches:
            start, end = positions[match.start], positions[match.end]
            if end > start:
                send(_Q.SCI_INDICATORFILLRANGE, start, end - start)
        for match in self.result.matches:
            for number, group in enumerate(match.groups):
                if group.start >= 0 and group.end > group.start:
                    send(
                        _Q.SCI_SETINDICATORCURRENT,
                        GROUP_INDICATORS[number % len(GROUP_INDICATORS)],
                    )
                    start = positions[group.start]
                    send(_Q.SCI_INDICATORFILLRANGE, start, positions[group.end] - start)

    def _fill_matches(self) -> None:
        self.matches.clear()
        for number, match in enumerate(self.result.matches[:500], 1):
            item = QTreeWidgetItem(
                [f"#{number}", f"{match.start}-{match.end}", _visible(match.text)]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, (match.start, match.end))
            colors = self.group_colors()
            for index, group in enumerate(match.groups):
                label = group.name if not group.name.isdigit() else f"${group.name}"
                child = QTreeWidgetItem(
                    [
                        label,
                        f"{group.start}-{group.end}" if group.start >= 0 else "",
                        _visible(group.text) if group.text is not None else tr("(no match)"),
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, (group.start, group.end))
                child.setForeground(0, QColor(colors[index % len(colors)]))
                item.addChild(child)
            self.matches.addTopLevelItem(item)
        if self.result.matches and len(self.result.matches) <= 20:
            self.matches.expandAll()

    def _picked(self, item: QTreeWidgetItem | None, _previous: object = None) -> None:
        if item is None:
            return
        span = item.data(0, Qt.ItemDataRole.UserRole)
        if not span or span[0] < 0:
            return
        text = str(self.text.text())
        positions = core.byte_offsets(text, span)
        self.text.SendScintilla(_Q.SCI_SETSEL, positions[span[0]], positions[span[1]])
        self.text.SendScintilla(_Q.SCI_SCROLLCARET)

    def _update_replace(self, pattern: str, flags: int, text: str) -> None:
        replacement = self.replacement.text()
        if not replacement or not pattern or self.result.error:
            self.replaced.hide()
            return
        outcome = core.replace(pattern, flags, text, replacement)
        self.replaced.show()
        self.replaced.setReadOnly(False)
        self.replaced.setText(outcome if isinstance(outcome, str) else outcome[0])
        self.replaced.setReadOnly(True)

    def copy_python(self) -> None:
        self.api.copy_to_clipboard(core.python_literal(self.pattern.text(), self.flag_value()))
        self.api.status(tr("Pattern copied as Python code."))

    def show(self) -> None:
        self.dialog.show()
        self.pattern.setFocus()


def _repolish(widget: QWidget) -> None:
    """Apply the style again after an object name or property changed."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


def _visible(text: str) -> str:
    """One line in the list: line breaks and tabs shown as symbols."""
    shown = text.replace("\r", "").replace("\n", "↵").replace("\t", "→")
    return shown if len(shown) <= 200 else shown[:197] + "..."


def open_regex_tester(api: ForgeAPI) -> RegexTester:
    editor = api.active_editor()
    text, pattern = SAMPLE, SAMPLE_PATTERN
    if editor is not None:
        if editor.has_selection() and "\n" not in editor.selected_text():
            pattern = editor.selected_text()  # a selected word or pattern
            text = editor.text()[:MAX_TEXT]
        elif editor.has_selection():
            text = editor.selected_text()[:MAX_TEXT]
        elif editor.text().strip():
            text = editor.text()[:MAX_TEXT]
            pattern = ""
    tester = RegexTester(api, text, pattern)
    tester.show()
    return tester

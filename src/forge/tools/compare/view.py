"""Side-by-side comparison view shown as a tab."""

from __future__ import annotations

from PyQt6.Qsci import QsciScintilla
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI, tr
from forge.themes import tokens
from forge.themes.theme import Theme
from forge.themes.tokens import mix
from forge.tools.compare.diff import ADDED, CHANGED, FILLER, REMOVED, Comparison, Row, compare

_Q = QsciScintilla
_MARKERS = {CHANGED: 20, ADDED: 21, REMOVED: 22, FILLER: 23}
_INLINE_INDICATOR = 9


def _colors(theme: Theme) -> dict[str, str]:
    """Added green, changed amber, removed red (raw brand hues, so the light
    theme gets clear tints instead of muddy darkened ones)."""
    bg = theme.editor_bg
    strength = 0.22 if theme.is_dark else 0.30
    return {
        CHANGED: mix(bg, tokens.WARNING, strength),
        ADDED: mix(bg, tokens.LIME, strength),
        REMOVED: mix(bg, tokens.ERROR, strength),
        FILLER: mix(bg, theme.border, 0.35),
        "inline": mix(bg, tokens.WARNING, 0.55 if theme.is_dark else 0.6),
    }


class CompareView(QWidget):
    def __init__(
        self,
        api: ForgeAPI,
        left_text: str,
        right_text: str,
        left_title: str,
        right_title: str,
    ) -> None:
        super().__init__()
        self.setObjectName("compareView")
        self._api = api
        self._texts = [left_text, right_text]
        self._titles = [left_title, right_title]
        self.comparison: Comparison = compare(left_text, right_text)
        self.left = api.create_viewer()
        self.right = api.create_viewer()
        self._syncing = False

        header = QHBoxLayout()
        header.setContentsMargins(10, 6, 10, 6)
        self.summary = QLabel(self)
        self.summary.setObjectName("findCount")
        previous = QToolButton(self)
        previous.setObjectName("findNav")
        previous.setText("↑")
        previous.setToolTip(tr("Previous Difference"))
        previous.clicked.connect(lambda: self.jump(-1))
        following = QToolButton(self)
        following.setObjectName("findNav")
        following.setText("↓")
        following.setToolTip(tr("Next Difference"))
        following.clicked.connect(lambda: self.jump(1))
        swap = QToolButton(self)
        swap.setObjectName("findNav")
        swap.setText("\u21c4")
        swap.setToolTip(tr("Swap Sides"))
        swap.clicked.connect(self.swap)
        header.addWidget(self.summary, 1)
        self._legend: dict[str, QLabel] = {}
        for kind, text in (
            (ADDED, tr("Added")),
            (CHANGED, tr("Changed")),
            (REMOVED, tr("Removed")),
        ):
            chip = QLabel(text, self)
            chip.setObjectName("compareLegend")
            self._legend[kind] = chip
            header.addWidget(chip)
        header.addSpacing(8)
        header.addWidget(swap)
        header.addWidget(previous)
        header.addWidget(following)

        titles = QHBoxLayout()
        titles.setContentsMargins(10, 0, 10, 4)
        self.left_label = QLabel(left_title, self)
        self.right_label = QLabel(right_title, self)
        for label in (self.left_label, self.right_label):
            label.setObjectName("compareTitle")
            titles.addWidget(label, 1)

        splitter = QSplitter(self)
        splitter.addWidget(self.left)
        splitter.addWidget(self.right)
        splitter.setChildrenCollapsible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addLayout(titles)
        layout.addWidget(splitter, 1)

        self.apply_theme(api.theme)
        self._load()
        self._link_scrolling()

    def swap(self) -> None:
        """Show the other document on the left (old) side."""
        self._texts.reverse()
        self._titles.reverse()
        self.comparison = compare(self._texts[0], self._texts[1])
        self.left_label.setText(self._titles[0])
        self.right_label.setText(self._titles[1])
        self._load()
        self.jump(1)

    def _load(self) -> None:
        self._fill(self.left, self.comparison.left)
        self._fill(self.right, self.comparison.right)
        self._update_summary()

    # Content ---------------------------------------------------------------

    def _fill(self, viewer: QsciScintilla, rows: list[Row]) -> None:
        viewer.SendScintilla(_Q.SCI_MARKERDELETEALL, -1)
        viewer.clearMarginText()
        viewer.setReadOnly(False)
        viewer.setText("\n".join(row.text for row in rows))
        viewer.setReadOnly(True)
        # Real line numbers (filler rows have none) in a text margin.
        viewer.setMarginType(0, _Q.MarginType.TextMarginRightJustified)
        widest = max((row.number or 0 for row in rows), default=0)
        viewer.setMarginWidth(0, "9" * (len(str(widest)) + 2))
        viewer.setMarginWidth(2, 0)  # no folding in a comparison
        for index, row in enumerate(rows):
            if row.number is not None:
                viewer.setMarginText(index, str(row.number), _Q.STYLE_LINENUMBER)
            marker = _MARKERS.get(row.kind)
            if marker is not None:
                # Raw Scintilla call: QsciScintilla.markerAdd ignores markers it
                # did not allocate itself.
                viewer.SendScintilla(_Q.SCI_MARKERADD, index, marker)
        viewer.SendScintilla(_Q.SCI_SETINDICATORCURRENT, _INLINE_INDICATOR)
        for index, row in enumerate(rows):
            if not row.inline:
                continue
            start = int(viewer.SendScintilla(_Q.SCI_POSITIONFROMLINE, index))
            for begin, end in row.inline:
                begin_bytes = len(row.text[:begin].encode("utf-8"))
                end_bytes = len(row.text[:end].encode("utf-8"))
                viewer.SendScintilla(
                    _Q.SCI_INDICATORFILLRANGE, start + begin_bytes, end_bytes - begin_bytes
                )

    def apply_theme(self, theme: Theme) -> None:
        colors = _colors(theme)
        for viewer in (self.left, self.right):
            for kind, marker in _MARKERS.items():
                viewer.SendScintilla(_Q.SCI_MARKERDEFINE, marker, _Q.SC_MARK_BACKGROUND)
                viewer.SendScintilla(_Q.SCI_MARKERSETBACK, marker, QColor(colors[kind]))
            viewer.SendScintilla(_Q.SCI_INDICSETSTYLE, _INLINE_INDICATOR, _Q.INDIC_FULLBOX)
            viewer.SendScintilla(_Q.SCI_INDICSETFORE, _INLINE_INDICATOR, QColor(colors["inline"]))
            viewer.SendScintilla(_Q.SCI_INDICSETALPHA, _INLINE_INDICATOR, 120)
            viewer.SendScintilla(_Q.SCI_INDICSETUNDER, _INLINE_INDICATOR, 1)
            viewer.setCaretLineVisible(False)
        for kind, chip in getattr(self, "_legend", {}).items():
            chip.setStyleSheet(
                f"background: {colors[kind]}; color: {theme.text}; border-radius: 4px;"
                " padding: 1px 8px; font-size: 11px;"
            )

    def _update_summary(self) -> None:
        c = self.comparison
        if c.identical:
            self.summary.setText(tr("No differences."))
            return
        self.summary.setText(
            tr(
                "{blocks} differences: {changed} changed, {added} added, {removed} removed lines",
                blocks=len(c.blocks),
                changed=c.changed,
                added=c.added,
                removed=c.removed,
            )
        )

    # Navigation --------------------------------------------------------------

    def _link_scrolling(self) -> None:
        for source, target in ((self.left, self.right), (self.right, self.left)):
            vertical = source.verticalScrollBar()
            horizontal = source.horizontalScrollBar()
            if vertical is not None:
                vertical.valueChanged.connect(
                    lambda value, t=target: self._sync(t.verticalScrollBar(), value)
                )
            if horizontal is not None:
                horizontal.valueChanged.connect(
                    lambda value, t=target: self._sync(t.horizontalScrollBar(), value)
                )

    def _sync(self, bar: object, value: int) -> None:
        if self._syncing or bar is None:
            return
        self._syncing = True
        try:
            bar.setValue(value)  # type: ignore[attr-defined]
        finally:
            self._syncing = False

    def jump(self, direction: int) -> None:
        blocks = self.comparison.blocks
        if not blocks:
            return
        current, _ = self.left.getCursorPosition()
        if direction > 0:
            target = next((b for b in blocks if b > current), blocks[0])
        else:
            target = next((b for b in reversed(blocks) if b < current), blocks[-1])
        for viewer in (self.left, self.right):
            viewer.setCursorPosition(target, 0)
            viewer.SendScintilla(_Q.SCI_ENSUREVISIBLEENFORCEPOLICY, target)
        self.left.setFirstVisibleLine(max(0, target - 3))
        self.left.setFocus()

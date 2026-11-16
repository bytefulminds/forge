"""Snipping Tool: capture an area or the whole screen, annotate, copy."""

from __future__ import annotations

import sys

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPoint, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QScreen,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI, tr
from forge.tools.utilities import capture
from forge.tools.utilities.annotate import Annotator

DELAYS = (0, 3, 5, 10)
HIDE_SETTLE_MS = 350  # time for the window to disappear before the grab


class RegionOverlay(QWidget):
    """The frozen screen, dimmed; drag a rectangle to keep that part."""

    chosen = pyqtSignal(QPixmap)
    cancelled = pyqtSignal()

    def __init__(self, shot: QPixmap, screen: QScreen) -> None:
        super().__init__(None)
        self.shot = shot
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(screen.geometry())
        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self._done = False

    def selection(self) -> QRect:
        if self._start is None or self._end is None:
            return QRect()
        a, b = self._start, self._end
        return QRect(min(a.x(), b.x()), min(a.y(), b.y()), abs(a.x() - b.x()), abs(a.y() - b.y()))

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.shot)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        area = self.selection()
        if not area.isEmpty():
            ratio = self.shot.devicePixelRatio()
            source = QRectF(
                area.x() * ratio, area.y() * ratio, area.width() * ratio, area.height() * ratio
            )
            painter.drawPixmap(QRectF(area), self.shot, source)
            pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(area.adjusted(0, 0, -1, -1))
            label = f"{round(area.width() * ratio)} x {round(area.height() * ratio)}"
            self._badge(painter, area.bottomLeft() + QPoint(0, 8), label)
        else:
            text = tr("Drag to select an area. Enter takes the whole screen, Esc cancels.")
            self._badge(painter, QPoint(self.width() // 2, 40), text, center=True)
        painter.end()

    def _badge(self, painter: QPainter, at: QPoint, text: str, center: bool = False) -> None:
        font = QFont()
        font.setPixelSize(13)
        painter.setFont(font)
        width = painter.fontMetrics().horizontalAdvance(text) + 20
        box = QRectF(at.x() - (width / 2 if center else 0), at.y(), width, 26)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 190))
        painter.drawRoundedRect(box, 6, 6)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._start = self._end = event.position().toPoint()
            self.update()
        elif event is not None and event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self._start is not None:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        area = self.selection()
        if area.width() > 3 and area.height() > 3:
            self._choose(area)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            area = self.selection()
            self._choose(area if not area.isEmpty() else self.rect())

    def _choose(self, area: QRect) -> None:
        if self._done:
            return
        self._done = True
        self.chosen.emit(crop(self.shot, area))
        self.close()

    def _cancel(self) -> None:
        if self._done:
            return
        self._done = True
        self.cancelled.emit()
        self.close()


def crop(shot: QPixmap, area: QRect) -> QPixmap:
    """``area`` in screen (logical) points, cropped at full resolution."""
    ratio = shot.devicePixelRatio()
    pixels = QRect(
        round(area.x() * ratio),
        round(area.y() * ratio),
        round(area.width() * ratio),
        round(area.height() * ratio),
    ).intersected(shot.rect())
    part = shot.copy(pixels)
    part.setDevicePixelRatio(ratio)
    return part


class SnipOptions:
    def __init__(self, area: bool, delay: int, hide: bool) -> None:
        self.area = area
        self.delay = delay
        self.hide = hide


def ask_options(api: ForgeAPI) -> SnipOptions | None:
    dialog = api.framed_dialog(tr("Snipping Tool"))
    body = dialog.body
    layout = QVBoxLayout(body)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(12)
    modes = QHBoxLayout()
    area = QToolButton(body)
    full = QToolButton(body)
    for button, icon, text in (
        (area, "square-dashed", tr("Area")),
        (full, "monitor", tr("Full screen")),
    ):
        button.setObjectName("snipMode")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setIcon(api.icon(icon))
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setMinimumSize(120, 70)
        modes.addWidget(button)
    (area if api.setting("snip_area", True) else full).setChecked(True)
    layout.addLayout(modes)

    row = QHBoxLayout()
    row.addWidget(QLabel(tr("Delay"), body))
    delay = QComboBox(body)
    for seconds in DELAYS:
        delay.addItem(tr("None") if seconds == 0 else tr("{n} seconds", n=seconds), seconds)
    saved_delay = api.setting("snip_delay", 0)
    delay.setCurrentIndex(max(0, delay.findData(saved_delay)))
    row.addWidget(delay, 1)
    layout.addLayout(row)
    hide = QCheckBox(tr("Hide Forge while capturing"), body)
    hide.setChecked(bool(api.setting("snip_hide", True)))
    layout.addWidget(hide)
    if capture.is_wayland() or sys.platform == "darwin":
        text = (
            tr("On Wayland your desktop shows its own screenshot window.")
            if capture.is_wayland()
            else tr("For an area, drag with the crosshair. Space picks a window, Esc cancels.")
        )
        note = QLabel(text, body)
        note.setObjectName("resultNote")
        note.setWordWrap(True)
        layout.addWidget(note)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, body
    )
    ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    ok.setText(tr("New Snip"))
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != dialog.DialogCode.Accepted:
        return None
    options = SnipOptions(area.isChecked(), int(delay.currentData()), hide.isChecked())
    api.set_setting("snip_area", options.area)
    api.set_setting("snip_delay", options.delay)
    api.set_setting("snip_hide", options.hide)
    return options


class Snipper(QObject):
    """Runs one snip: wait, grab, choose an area, annotate."""

    running: Snipper | None = None  # one snip at a time

    def __init__(self, api: ForgeAPI, options: SnipOptions) -> None:
        super().__init__(api.window)
        self.api = api
        self.options = options
        self.annotator: Annotator | None = None
        window = api.window
        # Started from the global shortcut while Forge was minimized or hidden:
        # it goes back there after the annotation window closes.
        self.was_minimized = window.isMinimized() or not window.isVisible()

    def start(self) -> None:
        busy = Snipper.running
        if busy is not None and not sip.isdeleted(busy):
            if busy.annotator is not None:  # still annotating: show that window again
                capture.bring_app_to_front()
                busy.annotator.bring_forward()
            self.deleteLater()
            return
        Snipper.running = self
        if not capture.mac_capture_allowed():
            self.api.inform(
                tr("Screen Recording"),
                tr(
                    "macOS needs your permission before Forge can take screenshots. "
                    "Allow Forge under System Settings > Privacy & Security > "
                    "Screen Recording, then start Forge again. When you run Forge "
                    "from source, allow the terminal or IDE that starts it instead."
                ),
            )
            self._done()
            return
        if self.options.hide and not self.was_minimized:
            self.api.window.hide()
        wait = self.options.delay * 1000 + (HIDE_SETTLE_MS if self.options.hide else 0)
        QTimer.singleShot(max(1, wait), self._grab)

    def _grab(self) -> None:
        if self.options.area and sys.platform == "darwin":
            screen = capture.screen_under_cursor()
            ratio = screen.devicePixelRatio() if screen is not None else 2.0
            capture.MacAreaCapture(self._from_desktop, ratio, self).start()
            return
        if capture.is_wayland():
            portal = capture.PortalScreenshot(self._from_desktop, self)
            portal.start(interactive=self.options.area)
            return
        screen = capture.screen_under_cursor()
        if screen is None:
            self._finish(None)
            return
        shot = capture.grab(screen)
        if not self.options.area:
            self._finish(shot)
            return
        overlay = RegionOverlay(shot, screen)
        overlay.chosen.connect(self._finish)
        overlay.cancelled.connect(lambda: self._finish(None))
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()
        overlay.setFocus()

    def _from_desktop(self, pixmap: QPixmap | None, error: str) -> None:
        if error:
            message = tr("The desktop did not take a screenshot: {error}", error=error)
            self.api.notify(message, "warning")
        self._finish(pixmap)

    def _finish(self, shot: QPixmap | None) -> None:
        window = self.api.window
        has_shot = shot is not None and not shot.isNull()
        if has_shot:
            capture.bring_app_to_front()
        if has_shot or (self.options.hide and not self.was_minimized):
            window.showNormal() if window.isMinimized() else window.show()
            window.raise_()
            window.activateWindow()
        if shot is not None and has_shot:
            self.annotator = Annotator(self.api, shot)
            self.annotator.exec()
        if self.was_minimized:
            window.showMinimized()
        self._done()

    def _done(self) -> None:
        if Snipper.running is self:
            Snipper.running = None
        self.deleteLater()


def saved_options(api: ForgeAPI) -> SnipOptions:
    """The choices of the last snip, without a delay: for the global shortcut."""
    return SnipOptions(
        bool(api.setting("snip_area", True)), 0, bool(api.setting("snip_hide", True))
    )


def snip_now(api: ForgeAPI) -> Snipper:
    """Start a snip right away (global shortcut, ``forge --snip``)."""
    snipper = Snipper(api, saved_options(api))
    snipper.start()
    return snipper


def open_snipping_tool(api: ForgeAPI) -> Snipper | None:
    options = ask_options(api)
    if options is None:
        return None
    snipper = Snipper(api, options)
    snipper.start()
    return snipper

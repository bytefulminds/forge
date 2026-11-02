"""Forge styled window header: a title bar row with the menu row below it.

The window is frameless on every platform so Forge looks the same on macOS,
Linux and Windows, but the window buttons follow the system: traffic lights
on the left on macOS, minimize, maximize and close on the right on Windows,
and the desktop's own button layout on Linux (see window_buttons). Dragging
the title bar moves the window, double-clicking maximizes (zooms), and
``EdgeResizer`` resizes from the edges.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QEnterEvent,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenuBar,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forge.i18n.translator import tr
from forge.themes import tokens
from forge.ui import window_buttons
from forge.ui.window_buttons import CLOSE, MAXIMIZE, MINIMIZE, ButtonLayout

IS_MAC = sys.platform == "darwin"
TITLE_BAR_HEIGHT = 34
RESIZE_MARGIN = 6
FLAT_BUTTON_WIDTH = 46
LIGHT_SIZE = 12  # diameter of a macOS traffic light
LIGHT_STEP = 20  # from one light to the next
LIGHT_MARGIN = 12  # from the window edge to the first light
STATUS_ICON_SIZE = 14  # unsaved / saved / reloaded, in front of the title

_LIGHT_COLORS = {CLOSE: tokens.MAC_CLOSE, MINIMIZE: tokens.MAC_MINIMIZE, MAXIMIZE: tokens.MAC_ZOOM}


def _tooltip(kind: str, mac: bool, expanded: bool = False) -> str:
    if kind == CLOSE:
        return tr("Close Window")
    if kind == MINIMIZE:
        return tr("Minimize")
    if mac:
        return tr("Exit Full Screen") if expanded else tr("Enter Full Screen")
    return tr("Restore") if expanded else tr("Maximize")


class WindowButton(QToolButton):
    """Minimize, maximize/restore or close: thin vector glyphs, or a macOS
    traffic light with ``mac``."""

    def __init__(self, kind: str, parent: QWidget | None = None, mac: bool = False) -> None:
        super().__init__(parent)
        self.kind = kind
        self.mac = mac
        self.maximized = False  # maximized, or full screen for a macOS zoom button
        self.active = True  # window has focus (macOS greys inactive lights)
        self.hovered_group = False  # macOS shows the glyphs when the group is hovered
        self.setObjectName(
            "windowLight" if mac else ("windowButtonClose" if kind == CLOSE else "windowButton")
        )
        if mac:
            self.setFixedSize(LIGHT_STEP, TITLE_BAR_HEIGHT)
        else:
            self.setFixedSize(FLAT_BUTTON_WIDTH, TITLE_BAR_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(_tooltip(kind, mac))
        self.setAccessibleName(self.toolTip())

    def set_maximized(self, maximized: bool) -> None:
        self.maximized = maximized
        self.setToolTip(_tooltip(self.kind, self.mac, maximized))
        self.update()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        if self.mac:
            self._paint_light()
            return
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(self.foregroundRole())
        if self.kind == CLOSE and self.underMouse():
            color = QColor(Qt.GlobalColor.white)
        pen = QPen(color)
        pen.setWidthF(1.1)
        painter.setPen(pen)
        c = QPointF(self.width() / 2, self.height() / 2)
        s = 5.0
        if self.kind == MINIMIZE:
            painter.drawLine(QPointF(c.x() - s, c.y()), QPointF(c.x() + s, c.y()))
        elif self.kind == MAXIMIZE and not self.maximized:
            painter.drawRect(QRectF(c.x() - s, c.y() - s, 2 * s, 2 * s))
        elif self.kind == MAXIMIZE:
            painter.drawRect(QRectF(c.x() - s, c.y() - s + 2, 2 * s - 2, 2 * s - 2))
            painter.drawPolyline(
                QPointF(c.x() - s + 2, c.y() - s + 2),
                QPointF(c.x() - s + 2, c.y() - s),
                QPointF(c.x() + s, c.y() - s),
                QPointF(c.x() + s, c.y() + s - 2),
                QPointF(c.x() + s - 2, c.y() + s - 2),
            )
        else:
            painter.drawLine(QPointF(c.x() - s, c.y() - s), QPointF(c.x() + s, c.y() + s))
            painter.drawLine(QPointF(c.x() - s, c.y() + s), QPointF(c.x() + s, c.y() - s))
        painter.end()

    def _paint_light(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = LIGHT_SIZE / 2
        if self.active or self.hovered_group:
            fill = QColor(_LIGHT_COLORS[self.kind])
            if self.isDown():
                fill = fill.darker(115)
        else:
            fill = QColor(self.palette().color(self.foregroundRole()))
            fill.setAlphaF(0.28)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawEllipse(c, r, r)
        if self.hovered_group:
            glyph = QColor(0, 0, 0, 150)
            pen = QPen(glyph)
            pen.setWidthF(1.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            g = 2.6
            if self.kind == CLOSE:
                painter.drawLine(QPointF(c.x() - g, c.y() - g), QPointF(c.x() + g, c.y() + g))
                painter.drawLine(QPointF(c.x() - g, c.y() + g), QPointF(c.x() + g, c.y() - g))
            elif self.kind == MINIMIZE:
                painter.drawLine(QPointF(c.x() - g - 0.6, c.y()), QPointF(c.x() + g + 0.6, c.y()))
            else:
                # Two small triangles pointing apart (in) or together (out of full screen).
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glyph)
                t = 3.2
                for sign in (-1, 1):
                    corner = QPointF(c.x() + sign * t, c.y() + sign * t)
                    if self.maximized:
                        corner = QPointF(c.x() + sign * 0.6, c.y() + sign * 0.6)
                    tip = -1 if self.maximized else 1
                    path = QPainterPath(corner)
                    path.lineTo(QPointF(corner.x() - sign * t * 1.15 * tip, corner.y()))
                    path.lineTo(QPointF(corner.x(), corner.y() - sign * t * 1.15 * tip))
                    path.closeSubpath()
                    painter.drawPath(path)
        painter.end()


class ButtonGroup(QWidget):
    """The window buttons on one side of a title bar. Hovering a group of
    macOS traffic lights shows the glyphs on all of them, as macOS does."""

    def __init__(self, kinds: tuple[str, ...], mac: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.mac = mac
        layout = QHBoxLayout(self)
        margin = LIGHT_MARGIN - (LIGHT_STEP - LIGHT_SIZE) // 2 if mac else 0
        layout.setContentsMargins(margin, 0, margin if mac else 0, 0)
        layout.setSpacing(0)
        self.buttons: dict[str, WindowButton] = {}
        for kind in kinds:
            button = WindowButton(kind, self, mac)
            layout.addWidget(button)
            self.buttons[kind] = button
        self.setFixedWidth(
            sum(b.width() for b in self.buttons.values()) + (2 * margin if kinds and mac else 0)
        )

    def enterEvent(self, event: QEnterEvent | None) -> None:
        self._hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent | None) -> None:
        self._hover(False)
        super().leaveEvent(event)

    def _hover(self, hovered: bool) -> None:
        if self.mac:
            for button in self.buttons.values():
                button.hovered_group = hovered
                button.update()

    def set_active(self, active: bool) -> None:
        for button in self.buttons.values():
            button.active = active
            button.update()


def build_groups(
    parent: QWidget, layout: ButtonLayout, only: tuple[str, ...] | None = None
) -> tuple[ButtonGroup, ButtonGroup]:
    """Left and right button groups; ``only`` limits the kinds (dialogs: close)."""

    def pick(kinds: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(k for k in kinds if only is None or k in only)

    left, right = pick(layout.left), pick(layout.right)
    if only is not None and not left and not right:
        right = only  # the desktop hides close; a dialog still needs one
    return ButtonGroup(left, layout.mac, parent), ButtonGroup(right, layout.mac, parent)


class TitleBar(QWidget):
    """Top row: window buttons where the system puts them, a centered title,
    and the app icon (not on macOS, where windows show none)."""

    def __init__(
        self,
        window: QWidget,
        icon: QIcon | None = None,
        parent: QWidget | None = None,
        layout_spec: ButtonLayout | None = None,
    ) -> None:
        super().__init__(parent or window)
        self._window = window
        self._drag_offset: QPoint | None = None
        self.button_layout = layout_spec or window_buttons.current()
        self.setObjectName("titleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setFixedHeight(TITLE_BAR_HEIGHT)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.icon = QLabel(self)
        self.icon.setObjectName("titleIcon")
        # The title with the document's state icon in front, centered together.
        self.title_area = QWidget(self)
        self.title_area.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.title_area.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        area = QHBoxLayout(self.title_area)
        area.setContentsMargins(0, 0, 0, 0)
        area.setSpacing(6)
        self.status_icon = QLabel(self.title_area)
        self.status_icon.setObjectName("titleStatus")
        self.status_icon.setFixedSize(STATUS_ICON_SIZE, STATUS_ICON_SIZE)
        self.status_icon.hide()
        self.status_kind: str | None = None
        self.title = QLabel(self.title_area)
        self.title.setObjectName("windowTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._full_title = ""
        area.addStretch(1)
        area.addWidget(self.status_icon)
        area.addWidget(self.title)
        area.addStretch(1)
        self.left_group, self.right_group = build_groups(self, self.button_layout)
        self.buttons = {**self.left_group.buttons, **self.right_group.buttons}
        for kind, button in self.buttons.items():
            button.clicked.connect(
                {
                    MINIMIZE: window.showMinimized,
                    MAXIMIZE: self._maximize_clicked,
                    CLOSE: window.close,
                }[kind]
            )

        left_width = self.left_group.width()
        right_width = self.right_group.width()
        row.addWidget(self.left_group)
        if icon is not None and not self.button_layout.mac and not self.left_group.buttons:
            self.icon.setPixmap(icon.pixmap(18, 18))
            row.addSpacing(10)
            row.addWidget(self.icon)
            left_width += 10 + 18
        else:
            self.icon.hide()
        # Balance both sides so the title is centered on the window.
        row.addSpacing(max(0, right_width - left_width))
        row.addWidget(self.title_area, 1)
        row.addSpacing(max(0, left_width - right_width))
        row.addWidget(self.right_group)
        window.windowTitleChanged.connect(self.set_title)

    # Title and document state ----------------------------------------------------------

    def set_title(self, text: str) -> None:
        self._full_title = text
        self._elide()

    def set_status(self, kind: str | None, pixmap: QPixmap | None, tooltip: str = "") -> None:
        """The icon in front of the title: unsaved, saved or reloaded (or none)."""
        self.status_kind = kind
        if kind is None or pixmap is None:
            self.status_icon.hide()
        else:
            self.status_icon.setPixmap(pixmap)
            self.status_icon.show()
        # The title area ignores the mouse (dragging); the tooltip goes on the bar.
        self.setToolTip(tooltip)
        self._elide()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        room = self.title_area.width()
        if self.status_icon.isVisible():
            room -= STATUS_ICON_SIZE + 6
        metrics = self.title.fontMetrics()
        text = metrics.elidedText(self._full_title, Qt.TextElideMode.ElideMiddle, max(0, room))
        self.title.setText(text)

    # Compatibility with the old fixed layout (tests, callers).
    @property
    def min_button(self) -> WindowButton | None:
        return self.buttons.get(MINIMIZE)

    @property
    def max_button(self) -> WindowButton | None:
        return self.buttons.get(MAXIMIZE)

    @property
    def close_button(self) -> WindowButton | None:
        return self.buttons.get(CLOSE)

    def _maximize_clicked(self) -> None:
        # The green macOS button means full screen; double-clicking the title
        # bar zooms (maximizes), as macOS does by default.
        if self.button_layout.mac:
            if self._window.isFullScreen():
                self._window.showNormal()
            else:
                self._window.showFullScreen()
        else:
            self.toggle_maximized()

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def update_state(self) -> None:
        button = self.max_button
        if button is not None:
            expanded = (
                self._window.isFullScreen()
                if self.button_layout.mac
                else self._window.isMaximized()
            )
            button.set_maximized(expanded)

    def set_active(self, active: bool) -> None:
        self.left_group.set_active(active)
        self.right_group.set_active(active)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            # The window system moves the window where supported (required on
            # Wayland). macOS and anything that refuses get a manual drag.
            if not IS_MAC and handle is not None and handle.startSystemMove():
                event.accept()
                return
            if not self._window.isMaximized():
                self._drag_offset = (
                    event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
                )
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if (
            event is not None
            and self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


_EDGE_CURSORS = {
    Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
    Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
}


class MenuRow(QWidget):
    """Second row: the menu bar, left aligned, inside the window."""

    def __init__(self, menu_bar: QMenuBar, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("menuRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        menu_bar.setNativeMenuBar(False)
        menu_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(0)
        layout.addWidget(menu_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)


class WindowHeader(QWidget):
    """Title bar on top of the menu row; installed with QMainWindow.setMenuWidget."""

    def __init__(self, window: QWidget, menu_bar: QMenuBar, icon: QIcon | None = None) -> None:
        super().__init__(window)
        self.setObjectName("windowHeader")
        self.title_bar = TitleBar(window, icon, self)
        self.menu_row = MenuRow(menu_bar, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title_bar)
        layout.addWidget(self.menu_row)


class EdgeResizer(QObject):
    """Lets a frameless window be resized from its edges (Linux)."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._cursor_overridden = False
        # Manual resize state, used when the platform has no system resize (macOS).
        self._resize_edges = Qt.Edge(0)
        self._press_pos = QPoint()
        self._start_geometry = QRect()

    def _edges(self, global_pos: QPoint) -> Qt.Edge:
        w = self._window
        if w.isMaximized() or w.isFullScreen():
            return Qt.Edge(0)
        pos = w.mapFromGlobal(global_pos)
        edges = Qt.Edge(0)
        if pos.x() <= RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        elif pos.x() >= w.width() - RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        elif pos.y() >= w.height() - RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges: Qt.Edge) -> Qt.CursorShape | None:
        top_left = Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        bottom_right = Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        top_right = Qt.Edge.TopEdge | Qt.Edge.RightEdge
        bottom_left = Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if edges in (top_left, bottom_right):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in (top_right, bottom_left):
            return Qt.CursorShape.SizeBDiagCursor
        return _EDGE_CURSORS.get(edges)

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if event is None or not isinstance(obj, QWidget) or obj.window() is not self._window:
            return False
        if event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            if self._resize_edges != Qt.Edge(0):
                self._resize_to(event.globalPosition().toPoint())
                return True
            if event.buttons() == Qt.MouseButton.NoButton:
                self._update_cursor(self._edges(event.globalPosition().toPoint()))
        elif event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                global_pos = event.globalPosition().toPoint()
                edges = self._edges(global_pos)
                handle = self._window.windowHandle()
                if edges != Qt.Edge(0):
                    if handle is not None and not IS_MAC and handle.startSystemResize(edges):
                        self._update_cursor(Qt.Edge(0))
                        return True
                    self._resize_edges = edges
                    self._press_pos = global_pos
                    self._start_geometry = self._window.geometry()
                    return True
        elif event.type() == QEvent.Type.MouseButtonRelease and self._resize_edges != Qt.Edge(0):
            self._resize_edges = Qt.Edge(0)
            self._update_cursor(Qt.Edge(0))
            return True
        elif event.type() == QEvent.Type.Leave and obj is self._window:
            self._update_cursor(Qt.Edge(0))
        return False

    def _resize_to(self, global_pos: QPoint) -> None:
        geometry = QRect(self._start_geometry)
        delta = global_pos - self._press_pos
        minimum = self._window.minimumSizeHint().expandedTo(self._window.minimumSize())
        edges = self._resize_edges
        if edges & Qt.Edge.LeftEdge:
            geometry.setLeft(min(geometry.left() + delta.x(), geometry.right() - minimum.width()))
        if edges & Qt.Edge.RightEdge:
            geometry.setRight(max(geometry.right() + delta.x(), geometry.left() + minimum.width()))
        if edges & Qt.Edge.TopEdge:
            geometry.setTop(min(geometry.top() + delta.y(), geometry.bottom() - minimum.height()))
        if edges & Qt.Edge.BottomEdge:
            geometry.setBottom(
                max(geometry.bottom() + delta.y(), geometry.top() + minimum.height())
            )
        self._window.setGeometry(geometry)

    def _update_cursor(self, edges: Qt.Edge) -> None:
        shape = self._cursor_for(edges)
        if shape is not None:
            if self._cursor_overridden:
                QApplication.changeOverrideCursor(QCursor(shape))
            else:
                QApplication.setOverrideCursor(QCursor(shape))
                self._cursor_overridden = True
        elif self._cursor_overridden:
            QApplication.restoreOverrideCursor()
            self._cursor_overridden = False

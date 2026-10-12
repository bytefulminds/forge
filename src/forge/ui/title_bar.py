"""Forge styled window header: a title bar row with the menu row below it.

The window is frameless on every platform so Forge looks the same on macOS,
Linux and Windows: icon on the left, centered title, and minimize, maximize
and close on the right. Dragging the title bar moves the window,
double-clicking maximizes, and ``EdgeResizer`` resizes from the edges.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QCursor, QIcon, QMouseEvent, QPainter, QPaintEvent, QPen
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

IS_MAC = sys.platform == "darwin"
TITLE_BAR_HEIGHT = 34
RESIZE_MARGIN = 6


class WindowButton(QToolButton):
    """Minimize, maximize/restore or close, drawn with thin vector glyphs."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.maximized = False
        self.setObjectName("windowButtonClose" if kind == "close" else "windowButton")
        self.setFixedSize(46, TITLE_BAR_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tooltips = {
            "minimize": tr("Minimize"),
            "maximize": tr("Maximize"),
            "close": tr("Close Window"),
        }
        self.setToolTip(tooltips[kind])

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(self.foregroundRole())
        if self.kind == "close" and self.underMouse():
            color = QColor(Qt.GlobalColor.white)
        pen = QPen(color)
        pen.setWidthF(1.1)
        painter.setPen(pen)
        c = QPointF(self.width() / 2, self.height() / 2)
        s = 5.0
        if self.kind == "minimize":
            painter.drawLine(QPointF(c.x() - s, c.y()), QPointF(c.x() + s, c.y()))
        elif self.kind == "maximize" and not self.maximized:
            painter.drawRect(QRectF(c.x() - s, c.y() - s, 2 * s, 2 * s))
        elif self.kind == "maximize":
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


class TitleBar(QWidget):
    """Top row: icon, centered title and window buttons."""

    def __init__(
        self, window: QWidget, icon: QIcon | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent or window)
        self._window = window
        self._drag_offset: QPoint | None = None
        self.setObjectName("titleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setFixedHeight(TITLE_BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.icon = QLabel(self)
        self.icon.setObjectName("titleIcon")
        self.title = QLabel(self)
        self.title.setObjectName("windowTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.min_button = WindowButton("minimize", self)
        self.max_button = WindowButton("maximize", self)
        self.close_button = WindowButton("close", self)
        self.min_button.clicked.connect(window.showMinimized)
        self.max_button.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(window.close)
        buttons = (self.min_button, self.max_button, self.close_button)

        left = 0
        if icon is not None:
            self.icon.setPixmap(icon.pixmap(18, 18))
            layout.addSpacing(10)
            layout.addWidget(self.icon)
            left = 10 + 18
        # Balance the window buttons so the title is centered on the window.
        layout.addSpacing(sum(b.width() for b in buttons) - left)
        layout.addWidget(self.title, 1)
        for button in buttons:
            layout.addWidget(button)
        window.windowTitleChanged.connect(self.title.setText)

    def toggle_maximized(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def update_state(self) -> None:
        self.max_button.maximized = self._window.isMaximized()
        self.max_button.setToolTip(tr("Restore") if self.max_button.maximized else tr("Maximize"))
        self.max_button.update()

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

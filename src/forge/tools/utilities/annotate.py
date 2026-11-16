"""Annotate a screenshot: rectangles, ellipses, lines, arrows, free pen, text
and a highlighter, in a chosen color and width. Select a shape to move or
resize it, crop the picture, erase shapes. OK copies the result."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, ClassVar

from PyQt6 import sip
from PyQt6.QtCore import QLineF, QPointF, QRectF, QSizeF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QShortcut,
    QTransform,
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QDialogButtonBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI, tr
from forge.themes import tokens
from forge.tools.widgets import InfoHint

TOOLS = (
    "select",
    "crop",
    "rect",
    "ellipse",
    "arrow",
    "line",
    "pen",
    "highlight",
    "text",
    "eraser",
)
DRAWING = ("rect", "ellipse", "arrow", "line", "pen", "highlight")
WIDTHS = (2, 4, 8)
HANDLE = 5.0  # half the size of a resize handle, in screen pixels
MIN_SIZE = 4.0
BRING_FORWARD_MS = (0, 150, 400, 900)


def tool_names() -> dict[str, str]:
    return {
        "select": tr("Select, move and resize"),
        "crop": tr("Crop"),
        "rect": tr("Rectangle"),
        "ellipse": tr("Ellipse"),
        "arrow": tr("Arrow"),
        "line": tr("Line"),
        "pen": tr("Pen"),
        "highlight": tr("Highlighter"),
        "text": tr("Text"),
        "eraser": tr("Eraser: click or drag over shapes to remove them"),
    }


TOOL_ICONS = {
    "select": "mouse-pointer-2",
    "crop": "crop",
    "rect": "square",
    "ellipse": "circle",
    "arrow": "arrow-up-right",
    "line": "slash",
    "pen": "pencil",
    "highlight": "highlighter",
    "text": "type",
    "eraser": "eraser",
}


def palette() -> tuple[str, ...]:
    """Annotation colors: red first (the usual "look here")."""
    return (
        tokens.ERROR,
        tokens.WARNING,
        tokens.LIME,
        tokens.SKY_BLUE,
        tokens.CYAN,
        tokens.WHITE,
        tokens.BLACK,
    )


class ArrowItem(QGraphicsPathItem):
    """A line with a filled arrow head at its end."""

    def __init__(self, line: QLineF, pen: QPen) -> None:
        super().__init__()
        self.setPen(pen)
        self.setBrush(QBrush(pen.color()))
        self.line = line
        self.set_line(line)

    def set_line(self, line: QLineF) -> None:
        self.line = QLineF(line)
        width = self.pen().widthF()
        head = max(12.0, width * 4.0)
        angle = math.atan2(line.dy(), line.dx())
        tip = line.p2()
        left = tip - QPointF(math.cos(angle - 0.45) * head, math.sin(angle - 0.45) * head)
        right = tip - QPointF(math.cos(angle + 0.45) * head, math.sin(angle + 0.45) * head)
        base = (left + right) / 2
        path = QPainterPath(line.p1())
        path.lineTo(base)
        path.addPolygon(QPolygonF([tip, left, right, tip]))
        self.setPath(path)


# Shape state (for undo) and handles ---------------------------------------------


def capture_state(item: QGraphicsItem) -> dict[str, Any]:
    state: dict[str, Any] = {"pos": item.pos(), "transform": item.transform()}
    if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
        state["rect"] = item.rect()
    if isinstance(item, ArrowItem):
        state["line"] = QLineF(item.line)
    elif isinstance(item, QGraphicsLineItem):
        state["line"] = item.line()
    elif isinstance(item, QGraphicsPathItem):
        state["path"] = item.path()
    if isinstance(item, QGraphicsTextItem):
        state["color"] = item.defaultTextColor()
    elif isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem,
                           QGraphicsPathItem)):  # fmt: skip
        state["pen"] = QPen(item.pen())
    return state


def apply_state(item: QGraphicsItem, state: dict[str, Any]) -> None:
    item.setPos(state["pos"])
    item.setTransform(state["transform"])
    if "pen" in state and isinstance(
        item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem)
    ):
        item.setPen(state["pen"])
        if isinstance(item, ArrowItem):
            item.setBrush(QBrush(state["pen"].color()))
    if "color" in state and isinstance(item, QGraphicsTextItem):
        item.setDefaultTextColor(state["color"])
    if "rect" in state and isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
        item.setRect(state["rect"])
    if "line" in state:
        if isinstance(item, ArrowItem):
            item.set_line(state["line"])
        elif isinstance(item, QGraphicsLineItem):
            item.setLine(state["line"])
    elif "path" in state and isinstance(item, QGraphicsPathItem):
        item.setPath(state["path"])


def _is_line(item: QGraphicsItem) -> bool:
    return isinstance(item, (QGraphicsLineItem, ArrowItem))


def _line_of(item: QGraphicsItem) -> QLineF:
    if isinstance(item, ArrowItem):
        return QLineF(item.line)
    assert isinstance(item, QGraphicsLineItem)
    return item.line()


def frame_of(item: QGraphicsItem) -> QRectF:
    """The rectangle the resize handles sit on, in scene coordinates."""
    if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
        return item.mapRectToScene(item.rect())
    return item.sceneBoundingRect()


def handles_of(item: QGraphicsItem) -> list[tuple[str, QPointF]]:
    """(name, scene point) for each handle: "p1"/"p2" for lines, else the
    corners and edge middles ("tl", "t", "tr", "r", "br", "b", "bl", "l")."""
    if _is_line(item):
        line = _line_of(item)
        return [("p1", item.mapToScene(line.p1())), ("p2", item.mapToScene(line.p2()))]
    return rect_handles(frame_of(item))


def rect_handles(r: QRectF) -> list[tuple[str, QPointF]]:
    cx, cy = r.center().x(), r.center().y()
    return [
        ("tl", r.topLeft()),
        ("t", QPointF(cx, r.top())),
        ("tr", r.topRight()),
        ("r", QPointF(r.right(), cy)),
        ("br", r.bottomRight()),
        ("b", QPointF(cx, r.bottom())),
        ("bl", r.bottomLeft()),
        ("l", QPointF(r.left(), cy)),
    ]


def resized(frame: QRectF, handle: str, point: QPointF) -> QRectF:
    """``frame`` with the edges of ``handle`` moved to ``point``."""
    left, top, right, bottom = frame.left(), frame.top(), frame.right(), frame.bottom()
    if "l" in handle:
        left = min(point.x(), right - MIN_SIZE)
    if "r" in handle:
        right = max(point.x(), left + MIN_SIZE)
    if handle.startswith("t"):
        top = min(point.y(), bottom - MIN_SIZE)
    if handle.startswith("b"):
        bottom = max(point.y(), top + MIN_SIZE)
    return QRectF(QPointF(left, top), QPointF(right, bottom))


def resize_item(item: QGraphicsItem, start: dict[str, Any], handle: str, point: QPointF) -> None:
    """Resize ``item`` from its ``start`` state by dragging ``handle`` to ``point``."""
    apply_state(item, start)
    if _is_line(item):
        line = _line_of(item)
        local = item.mapFromScene(point)
        new = QLineF(local, line.p2()) if handle == "p1" else QLineF(line.p1(), local)
        if isinstance(item, ArrowItem):
            item.set_line(new)
        elif isinstance(item, QGraphicsLineItem):
            item.setLine(new)
        return
    frame = frame_of(item)
    target = resized(frame, handle, point)
    if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
        item.setRect(item.mapRectFromScene(target))
        return
    # Pen strokes and text: scale around the opposite side.
    sx = target.width() / frame.width() if frame.width() else 1.0
    sy = target.height() / frame.height() if frame.height() else 1.0
    if isinstance(item, QGraphicsTextItem):  # text keeps its proportions
        uniform = sy if handle in ("t", "b") else sx if handle in ("l", "r") else max(sx, sy)
        sx = sy = max(uniform, 0.2)
    anchor_x = frame.right() if "l" in handle else frame.left()
    anchor_y = frame.bottom() if handle.startswith("t") else frame.top()
    anchor = item.mapFromScene(QPointF(anchor_x, anchor_y))
    scale = (
        QTransform()
        .translate(anchor.x(), anchor.y())
        .scale(sx, sy)
        .translate(-anchor.x(), -anchor.y())
    )
    item.setTransform(scale * start["transform"])


# The canvas ----------------------------------------------------------------------


class AnnotationView(QGraphicsView):
    def __init__(self, editor: Annotator) -> None:
        super().__init__(editor.scene)
        self.editor = editor
        self.setObjectName("annotateCanvas")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        self._start: QPointF | None = None
        self._item: QGraphicsItem | None = None
        self._handle: str | None = None
        self._crop_start: QRectF | None = None  # the crop frame when a drag began
        self._before: dict[QGraphicsItem, dict[str, Any]] = {}

    # Handles -------------------------------------------------------------------

    def selected_shape(self) -> QGraphicsItem | None:
        selected = [i for i in self.editor.scene.selectedItems() if i in self.editor.items]
        return selected[0] if len(selected) == 1 else None

    def handle_at(self, view_point: QPointF) -> str | None:
        if self.editor.tool == "crop":
            points = rect_handles(self.editor.pending_crop)
        else:
            item = self.selected_shape()
            if item is None or self.editor.tool != "select":
                return None
            points = handles_of(item)
        for name, point in points:
            spot = self.mapFromScene(point)
            if (
                abs(spot.x() - view_point.x()) <= HANDLE + 2
                and abs(spot.y() - view_point.y()) <= HANDLE + 2
            ):
                return name
        return None

    def drawForeground(self, painter: QPainter | None, rect: QRectF) -> None:
        if painter is None:
            return
        scale = self.transform().m11() or 1.0
        viewport = self.viewport()
        assert viewport is not None
        everything = self.mapToScene(viewport.rect()).boundingRect()
        outside = QPainterPath()
        outside.addRect(everything.united(self.editor.full))
        if self.editor.tool == "crop":
            self._draw_crop_frame(painter, outside, scale)
            return
        # Hide what was cropped away: the view shows more than the scene rect
        # when the window is wider or taller than the picture.
        outside.addRect(self.editor.crop)
        painter.fillPath(outside, self.backgroundBrush())
        if self.editor.tool != "select":
            return
        item = self.selected_shape()
        if item is None:
            return
        size = HANDLE / scale
        painter.setPen(QPen(QColor(tokens.SKY_BLUE), 1.0 / scale))
        painter.setBrush(QColor(tokens.WHITE))
        if not _is_line(item):
            outline = QPen(QColor(tokens.SKY_BLUE), 1.0 / scale, Qt.PenStyle.DashLine)
            painter.save()
            painter.setPen(outline)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(frame_of(item))
            painter.restore()
        for _name, point in handles_of(item):
            painter.drawRect(QRectF(point.x() - size, point.y() - size, size * 2, size * 2))

    def _draw_crop_frame(self, painter: QPainter, outside: QPainterPath, scale: float) -> None:
        """The whole picture, dimmed outside the frame, with handles to drag."""
        frame = self.editor.pending_crop
        outside.addRect(frame)
        painter.fillPath(outside, QColor(0, 0, 0, 140))
        painter.setPen(QPen(QColor(tokens.WHITE), 1.5 / scale))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(frame)
        painter.setPen(QPen(QColor(255, 255, 255, 90), 1.0 / scale))
        for i in (1, 2):  # rule of thirds
            x = frame.left() + frame.width() * i / 3
            y = frame.top() + frame.height() * i / 3
            painter.drawLine(QPointF(x, frame.top()), QPointF(x, frame.bottom()))
            painter.drawLine(QPointF(frame.left(), y), QPointF(frame.right(), y))
        size = HANDLE / scale
        painter.setPen(QPen(QColor(tokens.SKY_BLUE), 1.0 / scale))
        painter.setBrush(QColor(tokens.WHITE))
        for _name, point in rect_handles(frame):
            painter.drawRect(QRectF(point.x() - size, point.y() - size, size * 2, size * 2))

    _CURSORS: ClassVar[dict[str, Qt.CursorShape]] = {
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
        "t": Qt.CursorShape.SizeVerCursor,
        "b": Qt.CursorShape.SizeVerCursor,
        "l": Qt.CursorShape.SizeHorCursor,
        "r": Qt.CursorShape.SizeHorCursor,
        "p1": Qt.CursorShape.SizeAllCursor,
        "p2": Qt.CursorShape.SizeAllCursor,
    }

    # Mouse ---------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        tool = self.editor.tool
        point = self.mapToScene(event.position().toPoint())
        if tool == "select":
            handle = self.handle_at(event.position())
            item = self.selected_shape()
            if handle is not None and item is not None:
                self._handle = handle
                self._item = item
                self._before = {item: capture_state(item)}
                return
            super().mousePressEvent(event)
            self._before = {
                i: capture_state(i)
                for i in self.editor.scene.selectedItems()
                if i in self.editor.items
            }
            self.viewport().update()  # type: ignore[union-attr]
            return
        if tool == "text":
            self.editor.add_text(point)
            return
        if tool == "eraser":
            self._start = point
            self.editor.erase_at(point)
            return
        if tool == "crop":
            self._start = point
            self._crop_start = QRectF(self.editor.pending_crop)
            handle = self.handle_at(event.position())
            if handle is None and not self.editor.pending_crop.contains(point):
                handle = "new"  # draw a new frame
            self._handle = handle or "move"
            return
        self._start = point
        self._item = self.editor.begin_shape(point)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        point = self.mapToScene(event.position().toPoint())
        if self._crop_start is not None and self._start is not None and self._handle:
            self.editor.drag_crop(self._crop_start, self._handle, self._start, point)
            self.viewport().update()  # type: ignore[union-attr]
            return
        if self.editor.tool == "crop" and not event.buttons():
            handle = self.handle_at(event.position())
            if handle:
                cursor = self._CURSORS[handle]
            elif self.editor.pending_crop.contains(point):
                cursor = Qt.CursorShape.SizeAllCursor
            else:
                cursor = Qt.CursorShape.CrossCursor
            self.viewport().setCursor(cursor)  # type: ignore[union-attr]
            return
        if self._handle is not None and self._item is not None:
            resize_item(self._item, self._before[self._item], self._handle, point)
            self.viewport().update()  # type: ignore[union-attr]
            return
        if self.editor.tool == "select" and not event.buttons():
            handle = self.handle_at(event.position())
            self.viewport().setCursor(  # type: ignore[union-attr]
                self._CURSORS[handle] if handle else Qt.CursorShape.ArrowCursor
            )
        if self.editor.tool == "eraser" and self._start is not None:
            self.editor.erase_at(point)
            return
        if self._start is None or self._item is None:
            super().mouseMoveEvent(event)
            if self.editor.tool == "select" and event.buttons():
                self.viewport().update()  # type: ignore[union-attr]
            return
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self.editor.drag_shape(self._item, self._start, point, shift)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if self._crop_start is not None:
            pass  # the frame stays editable until Apply Crop, Enter or another tool
        elif self._handle is not None:
            self.editor.record_changes(self._before)
        elif self.editor.tool == "select":
            super().mouseReleaseEvent(event)
            self.editor.record_changes(self._before)
        elif self._item is not None:
            self.editor.finish_shape(self._item)
        self._start = None
        self._item = None
        self._crop_start = None
        self._handle = None
        self._before = {}
        self.viewport().update()  # type: ignore[union-attr]

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        if event is not None and self.editor.tool == "select":
            item = self.itemAt(event.position().toPoint())
            while item is not None and item not in self.editor.items:
                item = item.parentItem()
            if isinstance(item, QGraphicsTextItem):
                self.editor.edit_text(item)
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        enter = event is not None and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if enter and self.editor.tool == "crop":
            self.editor.apply_crop()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self.editor.fit()


# The window ----------------------------------------------------------------------


class Annotator:
    """The annotation window for one screenshot."""

    def __init__(self, api: ForgeAPI, shot: QPixmap) -> None:
        self.api = api
        self.shot = shot
        self.tool = "rect"
        self.color = QColor(palette()[0])
        self.width = WIDTHS[1]
        self.items: list[QGraphicsItem] = []  # the shapes on the picture
        self.history: list[Callable[[], None]] = []  # undo steps, newest last
        self.result = QImage()

        self.dialog = api.framed_dialog(tr("Snip and Annotate"), resizable=True)
        self.dialog.setProperty("forgeTool", self)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        size = shot.deviceIndependentSize()
        self.full = QRectF(QPointF(0, 0), QSizeF(size))
        self.crop = QRectF(self.full)
        self.pending_crop = QRectF(self.full)  # the frame while the crop tool is on
        self.scene = QGraphicsScene(self.dialog)
        self.background = QGraphicsPixmapItem(shot)
        self.background.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.background.setZValue(-1)
        self.scene.addItem(self.background)
        self.scene.setSceneRect(self.crop)
        self.view = AnnotationView(self)
        self.view.setBackgroundBrush(QColor(api.theme.chrome_bg))

        layout.addLayout(self._toolbar(body))
        layout.addWidget(self.view, 1)

        bottom = QHBoxLayout()
        # How the current tool works: shortened to fit, the whole text on hover,
        # so a long tip never makes the window wider.
        self.info = InfoHint(self.api.icon("info"), body)
        bottom.addWidget(self.info, 1)
        buttons = QDialogButtonBox(body)
        save = QPushButton(tr("Save PNG..."), body)
        save.clicked.connect(self.save)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.ActionRole)
        ok = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        ok.setText(tr("Copy"))
        ok.setDefault(True)
        ok.setToolTip(tr("Copy the annotated image to the clipboard"))
        ok.clicked.connect(self.copy)
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        assert cancel is not None
        cancel.clicked.connect(self.dialog.reject)
        bottom.addWidget(buttons)
        layout.addLayout(bottom)

        undo = QShortcut(QKeySequence(QKeySequence.StandardKey.Undo), self.dialog)
        undo.activated.connect(self.undo)
        for key in (QKeySequence.StandardKey.Delete, QKeySequence.StandardKey.Backspace):
            remove = QShortcut(QKeySequence(key), self.dialog)
            remove.activated.connect(self.delete_selected)

        screen = self.dialog.screen()
        available = screen.availableGeometry().size() if screen is not None else None
        width = min(size.width() + 60, (available.width() * 0.9) if available else 1400)
        height = min(size.height() + 170, (available.height() * 0.9) if available else 900)
        self.dialog.resize(max(760, round(width)), max(480, round(height)))
        self.set_tool(self.tool)

    # Toolbar ---------------------------------------------------------------------

    def _toolbar(self, body: QWidget) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.tool_buttons: dict[str, QToolButton] = {}
        group = QButtonGroup(body)
        names = tool_names()
        for tool in TOOLS:
            if tool in ("rect", "eraser"):
                bar.addSpacing(8)
            button = QToolButton(body)
            button.setObjectName("docToolButton")
            button.setCheckable(True)
            button.setIcon(self.api.icon(TOOL_ICONS[tool]))
            button.setToolTip(names[tool])
            button.clicked.connect(lambda _c=False, t=tool: self.set_tool(t))
            group.addButton(button)
            self.tool_buttons[tool] = button
            bar.addWidget(button)
        bar.addSpacing(12)
        self.swatches: list[QToolButton] = []
        for color in palette():
            swatch = QToolButton(body)
            swatch.setObjectName("colorSwatch")
            swatch.setCheckable(True)
            swatch.setAutoExclusive(True)
            swatch.setFixedSize(22, 22)
            swatch.setStyleSheet(f"QToolButton#colorSwatch {{ background: {color}; }}")
            swatch.setChecked(QColor(color) == self.color)
            swatch.clicked.connect(lambda _c=False, value=color: self.set_color(QColor(value)))
            self.swatches.append(swatch)
            bar.addWidget(swatch)
        more = QToolButton(body)
        more.setObjectName("docToolButton")
        more.setText("+")
        more.setToolTip(tr("Other color..."))
        more.clicked.connect(self.pick_color)
        bar.addWidget(more)
        bar.addSpacing(12)
        self.width_box = QComboBox(body)
        for width, name in zip(WIDTHS, (tr("Thin"), tr("Medium"), tr("Thick")), strict=True):
            self.width_box.addItem(name, width)
        self.width_box.setCurrentIndex(WIDTHS.index(self.width))
        self.width_box.currentIndexChanged.connect(
            lambda _i: self.set_width(int(self.width_box.currentData()))
        )
        bar.addWidget(self.width_box)
        bar.addStretch(1)
        self.apply_crop_button = QPushButton(tr("Apply Crop"), body)
        self.apply_crop_button.setProperty("primary", True)
        self.apply_crop_button.clicked.connect(self.apply_crop)
        self.apply_crop_button.hide()
        bar.addWidget(self.apply_crop_button)
        undo = QToolButton(body)
        undo.setObjectName("docToolButton")
        undo.setIcon(self.api.icon("undo-2"))
        undo.setToolTip(tr("Undo"))
        undo.clicked.connect(self.undo)
        bar.addWidget(undo)
        return bar

    def _hints(self) -> dict[str, str]:
        return {
            "select": tr(
                "Click a shape to select it, drag to move it, drag a handle to resize it. "
                "Double-click text to edit it. Delete removes it."
            ),
            "crop": tr(
                "Drag the handles or the frame to choose the part to keep, or drag a new "
                "frame. Enter or another tool applies the crop; Ctrl+Z undoes it."
            ),
            "text": tr("Click where the text goes, then type."),
            "eraser": tr("Click or drag over shapes to remove them."),
        }

    def set_tool(self, tool: str) -> None:
        if self.tool == "crop" and tool != "crop":
            self.tool = tool
            self.apply_crop()
        if tool == "crop":
            self.pending_crop = QRectF(self.crop)
            self.scene.setSceneRect(self.full)  # show the whole picture again
            self.fit()
        self.apply_crop_button.setVisible(tool == "crop")
        self.tool = tool
        self.tool_buttons[tool].setChecked(True)
        selecting = tool == "select"
        for item in self.items:
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, selecting)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, selecting)
            if isinstance(item, QGraphicsTextItem) and not selecting:
                self._stop_editing(item)
        if not selecting:
            self.scene.clearSelection()
        self.view.setDragMode(
            QGraphicsView.DragMode.RubberBandDrag if selecting else QGraphicsView.DragMode.NoDrag
        )
        cursor = {
            "select": Qt.CursorShape.ArrowCursor,
            "text": Qt.CursorShape.IBeamCursor,
            "eraser": Qt.CursorShape.PointingHandCursor,
        }.get(tool, Qt.CursorShape.CrossCursor)
        viewport = self.view.viewport()
        if viewport is not None:
            viewport.setCursor(cursor)
            viewport.update()
        self.info.set_text(
            self._hints().get(
                tool,
                tr("Drag to draw. Shift keeps lines straight and shapes square. Ctrl+Z undoes."),
            )
        )

    def set_color(self, color: QColor) -> None:
        self.color = color
        selected = [i for i in self.scene.selectedItems() if i in self.items]
        if selected:
            before = {item: capture_state(item) for item in selected}
            for item in selected:
                self._recolor(item, color)
            self.record_changes(before)

    def set_width(self, width: int) -> None:
        self.width = width
        selected = [i for i in self.scene.selectedItems() if i in self.items]
        before = {item: capture_state(item) for item in selected}
        for item in selected:
            if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem,
                                 QGraphicsPathItem)):  # fmt: skip
                pen = item.pen()
                highlight = pen.color().alpha() < 255
                pen.setWidthF(width * 4.0 if highlight else float(width))
                item.setPen(pen)
                if isinstance(item, ArrowItem):
                    item.set_line(item.line)
        self.record_changes(before)

    def pick_color(self) -> None:
        color = QColorDialog.getColor(self.color, self.dialog, tr("Annotation Color"))
        if color.isValid():
            for swatch in self.swatches:
                swatch.setAutoExclusive(False)
                swatch.setChecked(False)
                swatch.setAutoExclusive(True)
            self.set_color(color)

    # Drawing ---------------------------------------------------------------------

    def pen(self, highlight: bool = False) -> QPen:
        color = QColor(self.color)
        width = float(self.width)
        if highlight:
            color.setAlpha(90)
            width = width * 4
        pen = QPen(color, width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap if highlight else Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def begin_shape(self, point: QPointF) -> QGraphicsItem:
        tool = self.tool
        item: QGraphicsItem
        if tool == "rect":
            item = QGraphicsRectItem(QRectF(point, point))
            item.setPen(self.pen())
        elif tool == "ellipse":
            item = QGraphicsEllipseItem(QRectF(point, point))
            item.setPen(self.pen())
        elif tool == "line":
            item = QGraphicsLineItem(QLineF(point, point))
            item.setPen(self.pen())
        elif tool == "arrow":
            item = ArrowItem(QLineF(point, point), self.pen())
        else:  # pen, highlight
            item = QGraphicsPathItem(QPainterPath(point))
            item.setPen(self.pen(highlight=tool == "highlight"))
        self.scene.addItem(item)
        return item

    def drag_shape(self, item: QGraphicsItem, start: QPointF, point: QPointF, shift: bool) -> None:
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            if shift:  # square / circle
                side = max(abs(point.x() - start.x()), abs(point.y() - start.y()))
                point = QPointF(
                    start.x() + math.copysign(side, point.x() - start.x()),
                    start.y() + math.copysign(side, point.y() - start.y()),
                )
            item.setRect(QRectF(start, point).normalized())
        elif isinstance(item, (QGraphicsLineItem, ArrowItem)):
            if shift:  # snap to 45 degrees
                line = QLineF(start, point)
                line.setAngle(round(line.angle() / 45) * 45)
                point = line.p2()
            if isinstance(item, ArrowItem):
                item.set_line(QLineF(start, point))
            else:
                item.setLine(QLineF(start, point))
        elif isinstance(item, QGraphicsPathItem):
            path = item.path()
            if path.isEmpty():  # only its start point, which Qt does not keep
                path = QPainterPath(start)
            if shift:  # a straight horizontal stroke
                path = QPainterPath(start)
                path.lineTo(QPointF(point.x(), start.y()))
            else:
                path.lineTo(point)
            item.setPath(path)

    def finish_shape(self, item: QGraphicsItem) -> None:
        if item.boundingRect().width() < 2 and item.boundingRect().height() < 2:
            self.scene.removeItem(item)  # a click without a drag
            return
        self._add(item)

    def _add(self, item: QGraphicsItem) -> None:
        self.items.append(item)

        def undo() -> None:
            self.scene.removeItem(item)
            if item in self.items:
                self.items.remove(item)

        self.history.append(undo)

    def add_text(self, point: QPointF) -> None:
        item = QGraphicsTextItem()
        font = QFont()
        font.setPixelSize(12 + self.width * 3)
        font.setBold(True)
        item.setFont(font)
        item.setDefaultTextColor(self.color)
        item.setPlainText(tr("Text"))
        item.setPos(point)
        self.scene.addItem(item)
        self._add(item)
        self.edit_text(item)

    def edit_text(self, item: QGraphicsTextItem) -> None:
        item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        item.setFocus()
        cursor = item.textCursor()
        cursor.select(cursor.SelectionType.Document)
        item.setTextCursor(cursor)

    @staticmethod
    def _stop_editing(item: QGraphicsTextItem) -> None:
        cursor = item.textCursor()
        cursor.clearSelection()
        item.setTextCursor(cursor)
        item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        item.clearFocus()

    @staticmethod
    def _recolor(item: QGraphicsItem, color: QColor) -> None:
        if isinstance(item, QGraphicsTextItem):
            item.setDefaultTextColor(color)
            return
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem,
                             QGraphicsPathItem)):  # fmt: skip
            pen = item.pen()
            new = QColor(color)
            new.setAlpha(pen.color().alpha())
            pen.setColor(new)
            item.setPen(pen)
            if isinstance(item, ArrowItem):
                item.setBrush(QBrush(new))

    # Editing ---------------------------------------------------------------------

    def record_changes(self, before: dict[QGraphicsItem, dict[str, Any]]) -> None:
        """One undo step for shapes that were moved, resized or recolored."""
        changed = {item: state for item, state in before.items() if capture_state(item) != state}
        if not changed:
            return

        def undo() -> None:
            for item, state in changed.items():
                apply_state(item, state)

        self.history.append(undo)

    def _remove(self, items: list[QGraphicsItem]) -> None:
        for item in items:
            self.scene.removeItem(item)
            self.items.remove(item)

        def undo() -> None:
            for item in items:
                self.scene.addItem(item)
                self.items.append(item)

        self.history.append(undo)

    def erase_at(self, point: QPointF) -> None:
        near = QRectF(point.x() - 4, point.y() - 4, 8, 8)
        hit = [item for item in self.scene.items(near) if item in self.items]
        if hit:
            self._remove(hit)

    def delete_selected(self) -> None:
        selected = [i for i in self.scene.selectedItems() if i in self.items]
        if selected:
            self._remove(selected)

    def drag_crop(self, start: QRectF, handle: str, origin: QPointF, point: QPointF) -> None:
        """Change the crop frame: a handle resizes, "move" moves, "new" draws."""
        full = self.full
        if handle == "new":
            frame = QRectF(origin, point).normalized()
        elif handle == "move":
            frame = start.translated(point - origin)
            dx = max(0.0, full.left() - frame.left()) + min(0.0, full.right() - frame.right())
            dy = max(0.0, full.top() - frame.top()) + min(0.0, full.bottom() - frame.bottom())
            frame.translate(dx, dy)
        else:
            frame = resized(start, handle, point)
        frame = frame.intersected(full)
        if frame.width() >= MIN_SIZE and frame.height() >= MIN_SIZE:
            self.pending_crop = frame

    def apply_crop(self) -> None:
        """Crop to the frame (one undo step) and show only that part."""
        area = QRectF(self.pending_crop.toAlignedRect()).intersected(self.full)
        if area.width() < MIN_SIZE or area.height() < MIN_SIZE:
            area = QRectF(self.crop)
        if self.tool == "crop":
            self.set_tool("select")  # leaving the crop tool applies it
            return
        if area != self.crop:
            self.set_crop(area, record=True)
        else:
            self.scene.setSceneRect(self.crop)
            self.fit()

    def set_crop(self, area: QRectF, record: bool = False) -> None:
        previous = QRectF(self.crop)
        self.crop = QRectF(area)
        self.pending_crop = QRectF(area)
        if self.tool != "crop":
            self.scene.setSceneRect(self.crop)
        self.fit()
        if record:
            self.history.append(lambda: self.set_crop(previous))

    def undo(self) -> None:
        if self.history:
            self.history.pop()()
            self.view.viewport().update()  # type: ignore[union-attr]

    def fit(self) -> None:
        """Show the whole (cropped) picture, never larger than 100%."""
        rect = self.scene.sceneRect()
        view = self.view.viewport()
        if view is None or rect.isEmpty():
            return
        scale = min(1.0, (view.width() - 8) / rect.width(), (view.height() - 8) / rect.height())
        self.view.resetTransform()
        self.view.scale(scale, scale)
        self.view.centerOn(rect.center())

    # Output ----------------------------------------------------------------------

    def render(self) -> QImage:
        """The annotated (and cropped) screenshot at full (physical) resolution."""
        if self.tool == "crop":
            self.apply_crop()
        self.scene.clearSelection()
        for item in self.items:
            if isinstance(item, QGraphicsTextItem):
                self._stop_editing(item)
        ratio = self.shot.devicePixelRatio()
        width = max(1, round(self.crop.width() * ratio))
        height = max(1, round(self.crop.height() * ratio))
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.scene.render(painter, QRectF(0, 0, width, height), self.crop)
        painter.end()
        image.setDevicePixelRatio(ratio)
        return image

    def copy(self) -> None:
        self.result = self.render()
        self.api.copy_image(self.result)
        self.api.status(tr("Screenshot copied. Paste it where you like."))
        self.dialog.accept()

    def save(self) -> None:
        path = self.api.choose_save_file(
            tr("Save Screenshot"), "screenshot.png", [tr("PNG image (*.png)")]
        )
        if path is None:
            return
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png")
        self.result = self.render()
        if self.result.save(str(path), "PNG"):
            self.api.status(tr("Saved {name}.", name=path.name))
            self.dialog.accept()
        else:
            self.api.notify(tr("Could not save {name}.", name=path.name), "error")

    def exec(self) -> int:
        self.dialog.show()
        self.fit()
        # When Forge was in the background, the system may still be bringing the
        # main window forward; put this window on top again once that settled.
        for delay in BRING_FORWARD_MS:
            QTimer.singleShot(delay, self.bring_forward)
        return self.dialog.exec()

    def bring_forward(self) -> None:
        if not sip.isdeleted(self.dialog) and self.dialog.isVisible():
            self.dialog.raise_()
            self.dialog.activateWindow()

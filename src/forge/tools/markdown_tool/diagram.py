"""Draw Mermaid flowcharts with the mouse (Markdown toolbar > Diagram).

* Boxes snap to a grid while you drag them; the handles of a selected box
  resize it.
* Point at a box and four round connectors appear around it: drag one onto
  another box to connect them, or onto empty canvas to add a connected box.
* Double-click (or Enter) edits a label in place; Tab adds the next step.
* Every change is one undo step (Ctrl+Z, Ctrl+Shift+Z).

Forge writes the Mermaid code as you go (see flowchart.py) and puts it in the
document as a ```mermaid block, or replaces the block the cursor was in.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QLineF, QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyleOptionGraphicsItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import EditorHandle, ForgeAPI
from forge.i18n.translator import tr
from forge.themes.theme import Theme
from forge.tools.markdown_tool import flowchart as fc
from forge.tools.widgets import InfoHint

GRID = 10.0
CONNECTOR_RADIUS = 6.0
CONNECTOR_GAP = 16.0  # how far the connectors sit outside the box
HANDLE = 4.0
MIN_WIDTH, HEIGHT, PADDING = 110.0, 46.0, 18.0
SMALLEST = (40.0, 28.0)
NEW_BOX_DISTANCE = 40.0  # a link dropped this far from its box adds a new box
_MONO = "JetBrains Mono"
_UI = "Inter"


def code_font(size: int = 10) -> QFont:
    """JetBrains Mono without ligatures, so ``-->`` reads as typed."""
    font = QFont(_MONO, size)
    for tag in ("calt", "liga"):
        font.setFeature(QFont.Tag(tag), 0)
    return font


def _shape_names() -> dict[str, str]:
    return {
        "rect": tr("Box"),
        "round": tr("Rounded box"),
        "stadium": tr("Pill"),
        "diamond": tr("Decision"),
        "circle": tr("Circle"),
        "database": tr("Database"),
        "hexagon": tr("Hexagon"),
    }


def _edge_names() -> dict[str, str]:
    return {
        "arrow": tr("Arrow"),
        "line": tr("Line"),
        "dotted": tr("Dotted arrow"),
        "thick": tr("Thick arrow"),
    }


def _direction_names() -> dict[str, str]:
    return {
        "TD": tr("Top to bottom"),
        "LR": tr("Left to right"),
        "BT": tr("Bottom to top"),
        "RL": tr("Right to left"),
    }


def snap(value: float) -> float:
    return round(value / GRID) * GRID


def _resized(rect: QRectF, handle: str, point: QPointF) -> QRectF:
    """``rect`` with the edges of ``handle`` moved to ``point`` (never too small)."""
    left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
    min_w, min_h = SMALLEST
    if "l" in handle:
        left = min(snap(point.x()), right - min_w)
    if "r" in handle:
        right = max(snap(point.x()), left + min_w)
    if handle.startswith("t"):
        top = min(snap(point.y()), bottom - min_h)
    if handle.startswith("b"):
        bottom = max(snap(point.y()), top + min_h)
    return QRectF(QPointF(left, top), QPointF(right, bottom))


def _handle_points(r: QRectF) -> list[tuple[str, QPointF]]:
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


_HANDLE_CURSORS = {
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
    "t": Qt.CursorShape.SizeVerCursor,
    "b": Qt.CursorShape.SizeVerCursor,
    "l": Qt.CursorShape.SizeHorCursor,
    "r": Qt.CursorShape.SizeHorCursor,
}


# Canvas items -------------------------------------------------------------------------


class NodeItem(QGraphicsObject):
    """A box: drag to move, drag a handle to resize, drag a connector to link."""

    moved = pyqtSignal()

    def __init__(self, node: fc.Node, theme: Theme) -> None:
        super().__init__()
        self.node = node
        self.theme = theme
        self.edges: list[EdgeItem] = []
        self.hovered = False
        self.target = False  # highlighted as the end of a link being dragged
        self._resize: tuple[str, QRectF] | None = None
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setPos(node.x, node.y)
        self.setZValue(1)

    # Geometry
    def size(self) -> tuple[float, float]:
        if self.node.w and self.node.h:
            return self.node.w, self.node.h
        metrics = QFontMetricsF(QFont(_UI, 10))
        width = max(MIN_WIDTH, metrics.horizontalAdvance(self.node.label) + 2 * PADDING)
        height = HEIGHT
        if self.node.shape == "diamond":
            width, height = width * 1.25, HEIGHT * 1.5
        elif self.node.shape == "circle":
            width = height = max(width * 0.8, HEIGHT * 1.6)
        return snap(width), snap(height)

    def body(self) -> QRectF:
        width, height = self.size()
        return QRectF(-width / 2, -height / 2, width, height)

    def boundingRect(self) -> QRectF:
        reach = CONNECTOR_GAP + CONNECTOR_RADIUS + 2
        return self.body().adjusted(-reach, -reach, reach, reach)

    def connectors(self) -> list[QPointF]:
        r = self.body()
        gap = CONNECTOR_GAP
        return [
            QPointF(0, r.top() - gap),
            QPointF(r.right() + gap, 0),
            QPointF(0, r.bottom() + gap),
            QPointF(r.left() - gap, 0),
        ]

    def connector_at(self, local: QPointF) -> bool:
        if not (self.hovered or self.isSelected()):
            return False
        reach = CONNECTOR_RADIUS + 4
        return any(QLineF(local, p).length() <= reach for p in self.connectors())

    def handle_at(self, local: QPointF) -> str | None:
        if not self.isSelected():
            return None
        for name, point in _handle_points(self.body()):
            if (
                abs(local.x() - point.x()) <= HANDLE + 3
                and abs(local.y() - point.y()) <= HANDLE + 3
            ):
                return name
        return None

    def outline(self) -> QPainterPath:
        r = self.body()
        path = QPainterPath()
        shape = self.node.shape
        if shape == "round":
            path.addRoundedRect(r, 10, 10)
        elif shape == "stadium":
            path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        elif shape == "circle":
            path.addEllipse(r)
        elif shape == "diamond":
            path.addPolygon(QPolygonF([QPointF(0, r.top()), QPointF(r.right(), 0),
                                       QPointF(0, r.bottom()), QPointF(r.left(), 0),
                                       QPointF(0, r.top())]))  # fmt: skip
        elif shape == "hexagon":
            inset = min(r.height() / 2.5, r.width() / 4)
            path.addPolygon(QPolygonF([QPointF(r.left() + inset, r.top()),
                                       QPointF(r.right() - inset, r.top()),
                                       QPointF(r.right(), 0),
                                       QPointF(r.right() - inset, r.bottom()),
                                       QPointF(r.left() + inset, r.bottom()),
                                       QPointF(r.left(), 0),
                                       QPointF(r.left() + inset, r.top())]))  # fmt: skip
        elif shape == "database":
            ry = min(7.0, r.height() / 4)
            path.moveTo(r.left(), r.top() + ry)
            path.arcTo(QRectF(r.left(), r.top(), r.width(), 2 * ry), 180, -180)
            path.lineTo(r.right(), r.bottom() - ry)
            path.arcTo(QRectF(r.left(), r.bottom() - 2 * ry, r.width(), 2 * ry), 0, -180)
            path.closeSubpath()
        else:
            path.addRoundedRect(r, 3, 3)
        return path

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.body().adjusted(-HANDLE - 3, -HANDLE - 3, HANDLE + 3, HANDLE + 3))
        if self.hovered or self.isSelected():
            for point in self.connectors():
                path.addEllipse(point, CONNECTOR_RADIUS + 4, CONNECTOR_RADIUS + 4)
        return path

    def edge_point(self, toward: QPointF) -> QPointF:
        """Where a line from the center toward ``toward`` (scene) leaves the box."""
        center = self.scenePos()
        line = QLineF(center, toward)
        if line.length() == 0:
            return center
        outline = self.outline()
        r = self.body()
        reach = min(1.0, (r.width() + r.height()) / line.length())
        low, high = 0.0, reach
        for _ in range(18):  # bisect along the line to the outline
            middle = (low + high) / 2
            if outline.contains(self.mapFromScene(line.pointAt(middle))):
                low = middle
            else:
                high = middle
        return line.pointAt(low)

    def set_size(self, width: float, height: float) -> None:
        self.prepareGeometryChange()
        self.node.w, self.node.h = width, height
        for edge in self.edges:
            edge.update_path()
        self.update()

    # Painting
    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None:
            return
        t = self.theme
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = self.isSelected()
        accent = QColor(t.accent)
        if self.target:
            painter.setPen(QPen(accent, 3))
        else:
            painter.setPen(
                QPen(accent if selected else QColor(t.border_strong), 2 if selected else 1.2)
            )
        painter.setBrush(QBrush(QColor(t.elevated_bg)))
        painter.drawPath(self.outline())
        if self.node.shape == "database":
            r = self.body()
            ry = min(7.0, r.height() / 4)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(r.left(), r.top(), r.width(), 2 * ry), 180 * 16, 180 * 16)
        painter.setPen(QColor(t.text))
        painter.setFont(QFont(_UI, 10))
        painter.drawText(
            self.body().adjusted(6, 2, -6, -2),
            int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
            self.node.label,
        )
        if self.hovered or selected:
            painter.setPen(QPen(QColor(t.editor_bg), 1.5))
            painter.setBrush(accent)
            for point in self.connectors():
                painter.drawEllipse(point, CONNECTOR_RADIUS, CONNECTOR_RADIUS)
        if selected:
            painter.setPen(QPen(accent, 1))
            painter.setBrush(QColor(t.editor_bg))
            for _name, point in _handle_points(self.body()):
                painter.drawRect(
                    QRectF(point.x() - HANDLE, point.y() - HANDLE, 2 * HANDLE, 2 * HANDLE)
                )

    # Events
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        moving = change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
        if moving and isinstance(value, QPointF) and self._resize is None:
            return QPointF(snap(value.x()), snap(value.y()))  # moves snap to the grid
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = self.pos()
            self.node.x, self.node.y = pos.x(), pos.y()
            for edge in self.edges:
                edge.update_path()
            self.moved.emit()
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.prepareGeometryChange()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        self.prepareGeometryChange()
        self.hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        if event is not None:
            handle = self.handle_at(event.pos())
            if handle is not None:
                cursor = _HANDLE_CURSORS[handle]
            elif self.connector_at(event.pos()):
                cursor = Qt.CursorShape.CrossCursor
            else:
                cursor = Qt.CursorShape.SizeAllCursor
            self.setCursor(cursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        self.prepareGeometryChange()
        self.hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        scene = self.scene()
        if event is None or not isinstance(scene, DiagramScene):
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.handle_at(event.pos())
            if handle is not None:
                self._resize = (handle, self.mapRectToScene(self.body()))
                event.accept()
                return
            if self.connector_at(event.pos()):
                scene.start_link(self, event.scenePos())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        scene = self.scene()
        if event is None or not isinstance(scene, DiagramScene):
            return
        if self._resize is not None:
            handle, start = self._resize
            rect = _resized(start, handle, event.scenePos())
            self.set_size(rect.width(), rect.height())
            self.setPos(rect.center())
            return
        if scene.linking is not None:
            scene.drag_link(event.scenePos())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        scene = self.scene()
        if event is None or not isinstance(scene, DiagramScene):
            return
        if self._resize is not None:
            self._resize = None
            scene.commit()
            return
        if scene.linking is not None:
            scene.finish_link(event.scenePos())
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        scene = self.scene()
        if isinstance(scene, DiagramScene):
            scene.edit_requested.emit(self)


class EdgeItem(QGraphicsPathItem):
    """An arrow from one box to another, with an optional label."""

    def __init__(self, edge: fc.Edge, source: NodeItem, target: NodeItem, theme: Theme) -> None:
        super().__init__()
        self.edge = edge
        self.source = source
        self.target = target
        self.theme = theme
        self._end = QPointF()
        self._angle = 0.0
        source.edges.append(self)
        target.edges.append(self)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(0)
        self.update_path()

    def update_path(self) -> None:
        if self.source is self.target:  # a loop back to itself
            top = self.source.scenePos() - QPointF(0, self.source.body().height() / 2)
            path = QPainterPath(top + QPointF(-12, 0))
            path.cubicTo(top + QPointF(-30, -50), top + QPointF(30, -50), top + QPointF(12, 0))
            self._end = top + QPointF(12, 0)
            self._angle = math.atan2(-1, 0.4)
        else:
            start = self.source.edge_point(self.target.scenePos())
            end = self.target.edge_point(self.source.scenePos())
            path = QPainterPath(start)
            path.lineTo(end)
            self._end = end
            self._angle = math.atan2(start.y() - end.y(), start.x() - end.x())
        self.setPath(path)
        self.update()

    def label_point(self) -> QPointF:
        return self.path().pointAtPercent(0.5)

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(14)
        path = stroker.createStroke(self.path())
        if self.edge.label:
            middle = self.label_point()
            path.addRect(QRectF(middle.x() - 40, middle.y() - 12, 80, 24))
        return path

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-80, -20, 80, 20)

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None:
            return
        t = self.theme
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(t.accent if self.isSelected() else t.text_muted)
        style = self.edge.style
        pen = QPen(color, 3.0 if style == "thick" else 1.5)
        if style == "dotted":
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())
        if style != "line":
            draw_head(painter, self._end, self._angle, color, 10.0 if style == "thick" else 8.0)
        if self.edge.label:
            middle = self.label_point()
            font = QFont(_UI, 9)
            metrics = QFontMetricsF(font)
            width = metrics.horizontalAdvance(self.edge.label) + 10
            box = QRectF(middle.x() - width / 2, middle.y() - 10, width, 20)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(t.editor_bg))
            painter.drawRoundedRect(box, 4, 4)
            painter.setPen(QColor(t.text))
            painter.setFont(font)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, self.edge.label)


def draw_head(painter: QPainter, tip: QPointF, angle: float, color: QColor, size: float) -> None:
    head = QPolygonF([
        tip,
        tip + QPointF(math.cos(angle + 0.45) * size, math.sin(angle + 0.45) * size),
        tip + QPointF(math.cos(angle - 0.45) * size, math.sin(angle - 0.45) * size),
    ])  # fmt: skip
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(head)


class LinkPreview(QGraphicsPathItem):
    """The dashed arrow while you drag a connection."""

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self.color = QColor(theme.accent)
        self.setPen(QPen(self.color, 1.6, Qt.PenStyle.DashLine))
        self.setZValue(5)
        self.tip = QPointF()
        self.angle = 0.0

    def set_line(self, start: QPointF, end: QPointF) -> None:
        path = QPainterPath(start)
        path.lineTo(end)
        self.tip = end
        self.angle = math.atan2(start.y() - end.y(), start.x() - end.x())
        self.setPath(path)

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-12, -12, 12, 12)

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        if painter is None:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        super().paint(painter, option, widget)
        draw_head(painter, self.tip, self.angle, self.color, 8.0)


# The scene: the chart, its items, undo -----------------------------------------------


class DiagramScene(QGraphicsScene):
    """Holds the flowchart and its items; ``changed_chart`` after every edit."""

    changed_chart = pyqtSignal()
    edit_requested = pyqtSignal(object)  # a NodeItem or EdgeItem
    rebuilt = pyqtSignal()  # after undo or redo replaced every item

    def __init__(self, chart: fc.Flowchart, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chart = chart
        self.theme = theme
        self.nodes: dict[str, NodeItem] = {}
        self.linking: NodeItem | None = None
        self._preview: LinkPreview | None = None
        self._target: NodeItem | None = None
        self.setBackgroundBrush(QColor(theme.editor_bg))
        self._build()
        self.saved = fc.to_mermaid(chart)  # the state undo goes back to
        self.undo_stack: list[str] = []
        self.redo_stack: list[str] = []

    def _build(self) -> None:
        for node in self.chart.nodes:
            self._add_node_item(node)
        for edge in self.chart.edges:
            self._add_edge_item(edge)

    def drawBackground(self, painter: QPainter | None, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        if painter is None:
            return
        color = QColor(self.theme.border)
        painter.setPen(QPen(color, 1.6))
        step = GRID * 2
        x = math.floor(rect.left() / step) * step
        points = []
        while x < rect.right():
            y = math.floor(rect.top() / step) * step
            while y < rect.bottom():
                points.append(QPointF(x, y))
                y += step
            x += step
        painter.drawPoints(QPolygonF(points))

    def _add_node_item(self, node: fc.Node) -> NodeItem:
        item = NodeItem(node, self.theme)
        item.moved.connect(self.changed_chart)
        self.addItem(item)
        self.nodes[node.id] = item
        return item

    def _add_edge_item(self, edge: fc.Edge) -> EdgeItem | None:
        source, target = self.nodes.get(edge.source), self.nodes.get(edge.target)
        if source is None or target is None:
            return None
        item = EdgeItem(edge, source, target, self.theme)
        self.addItem(item)
        return item

    # Undo
    def commit(self) -> None:
        """Make the current state one undo step (when it changed)."""
        state = fc.to_mermaid(self.chart)
        if state != self.saved:
            self.undo_stack.append(self.saved)
            self.redo_stack.clear()
            self.saved = state
        self.changed_chart.emit()

    def _restore(self, state: str) -> None:
        selected = {i.node.id for i in self.selectedItems() if isinstance(i, NodeItem)}
        for item in list(self.items()):
            self.removeItem(item)
        self.nodes.clear()
        self.chart = fc.parse(state)
        self._build()
        self.saved = state
        for node_id in selected:
            if node_id in self.nodes:
                self.nodes[node_id].setSelected(True)
        self.rebuilt.emit()
        self.changed_chart.emit()

    def undo(self) -> None:
        if self.undo_stack:
            self.redo_stack.append(self.saved)
            self._restore(self.undo_stack.pop())

    def redo(self) -> None:
        if self.redo_stack:
            self.undo_stack.append(self.saved)
            self._restore(self.redo_stack.pop())

    # Editing
    def add_node(self, shape: str, at: QPointF, label: str | None = None) -> NodeItem:
        node = fc.Node(
            self.chart.new_id(), label or tr("New step"), shape, snap(at.x()), snap(at.y())
        )
        self.chart.nodes.append(node)
        item = self._add_node_item(node)
        self.clearSelection()
        item.setSelected(True)
        self.commit()
        return item

    def connect_nodes(self, source: NodeItem, target: NodeItem, select: bool = True) -> None:
        if any(e.source == source.node.id and e.target == target.node.id for e in self.chart.edges):
            return  # already connected
        edge = fc.Edge(source.node.id, target.node.id)
        self.chart.edges.append(edge)
        item = self._add_edge_item(edge)
        if item is not None and select:
            self.clearSelection()
            item.setSelected(True)
        self.commit()

    def add_next(self, source: NodeItem) -> NodeItem:
        """A new box one step further along the flow, connected to ``source``."""
        dx, dy = {
            "TD": (0, fc.LAYER_GAP),
            "BT": (0, -fc.LAYER_GAP),
            "LR": (fc.NODE_GAP, 0),
            "RL": (-fc.NODE_GAP, 0),
        }[self.chart.direction]
        at = source.pos() + QPointF(dx, dy)
        taken = [i.pos() for i in self.nodes.values()]
        sideways = QPointF(fc.NODE_GAP, 0) if dy else QPointF(0, fc.LAYER_GAP)
        while any(QLineF(at, p).length() < 30 for p in taken):  # beside a box already there
            at += sideways
        target = self.add_node("rect", at)
        self.connect_nodes(source, target, select=False)
        self.clearSelection()
        target.setSelected(True)
        return target

    def set_label(self, item: NodeItem | EdgeItem, text: str) -> None:
        if isinstance(item, NodeItem):
            item.prepareGeometryChange()
            item.node.label = text
            for edge in item.edges:
                edge.update_path()
        else:
            item.prepareGeometryChange()
            item.edge.label = text
        item.update()
        self.commit()

    def delete_selected(self) -> None:
        for item in list(self.selectedItems()):
            if isinstance(item, NodeItem) and item.scene() is self:
                for edge in list(item.edges):
                    self._remove_edge(edge)
                self.chart.nodes.remove(item.node)
                del self.nodes[item.node.id]
                self.removeItem(item)
            elif isinstance(item, EdgeItem) and item.scene() is self:
                self._remove_edge(item)
        self.commit()

    def _remove_edge(self, item: EdgeItem) -> None:
        if item.edge in self.chart.edges:
            self.chart.edges.remove(item.edge)
        for end in (item.source, item.target):
            if item in end.edges:
                end.edges.remove(item)
        if item.scene() is self:
            self.removeItem(item)

    def relayout(self) -> None:
        fc.auto_layout(self.chart)
        for node_id, item in self.nodes.items():
            node = self.chart.node(node_id)
            if node is not None:
                item.setPos(node.x, node.y)
        self.commit()

    def nudge(self, dx: float, dy: float) -> None:
        for item in self.selectedItems():
            if isinstance(item, NodeItem):
                item.setPos(item.pos() + QPointF(dx, dy))
        self.commit()

    # Connecting by dragging a connector
    def node_at(self, at: QPointF, other_than: NodeItem | None = None) -> NodeItem | None:
        for item in self.items(at):
            if not isinstance(item, NodeItem) or item is other_than:
                continue
            local = item.mapFromScene(at)
            if item.body().adjusted(-8, -8, 8, 8).contains(local):
                return item
        return None

    def start_link(self, source: NodeItem, at: QPointF) -> None:
        self.linking = source
        self._preview = LinkPreview(self.theme)
        self.addItem(self._preview)
        self.drag_link(at)

    def drag_link(self, at: QPointF) -> None:
        source = self.linking
        if source is None or self._preview is None:
            return
        target = self.node_at(at, other_than=source)
        if target is not self._target:
            for node in (self._target, target):
                if node is not None:
                    node.target = node is target
                    node.update()
            self._target = target
        end = target.edge_point(source.scenePos()) if target is not None else at
        self._preview.set_line(source.edge_point(end), end)

    def finish_link(self, at: QPointF) -> NodeItem | None:
        """Connect to the box under ``at``, or add a box there; returns a new box."""
        source = self.linking
        self.linking = None
        if self._preview is not None:
            self.removeItem(self._preview)
            self._preview = None
        if self._target is not None:
            self._target.target = False
            self._target.update()
        target = self.node_at(at, other_than=source) if source is not None else None
        self._target = None
        if source is None:
            return None
        if target is not None:
            self.connect_nodes(source, target)
            return None
        if QLineF(source.scenePos(), at).length() - max(source.size()) / 2 < NEW_BOX_DISTANCE:
            return None  # dropped right next to the box: nothing to do
        new = self.add_node("rect", at)
        self.connect_nodes(source, new, select=False)
        self.clearSelection()
        new.setSelected(True)
        self.edit_requested.emit(new)
        return new


class DiagramView(QGraphicsView):
    """The canvas: rubber band selection, double-click to add, keys, inline editing."""

    def __init__(self, scene: DiagramScene, on_add: Callable[[QPointF], None]) -> None:
        super().__init__(scene)
        self._on_add = on_add
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setMinimumSize(520, 360)
        self.setObjectName("diagramCanvas")
        self.editor: QLineEdit | None = None
        self._editing: NodeItem | EdgeItem | None = None

    def diagram(self) -> DiagramScene:
        scene = self.scene()
        assert isinstance(scene, DiagramScene)
        return scene

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        item = self.itemAt(event.pos())
        if isinstance(item, EdgeItem):
            self.edit_inline(item)
            return
        if item is None:
            self._on_add(self.mapToScene(event.pos()))
            return
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        super().mouseReleaseEvent(event)
        self.diagram().commit()  # a move becomes one undo step

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
        scene = self.diagram()
        key = event.key()
        selected = scene.selectedItems()
        single = selected[0] if len(selected) == 1 else None
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            scene.delete_selected()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2) and isinstance(
            single, NodeItem | EdgeItem
        ):
            self.edit_inline(single)
        elif key == Qt.Key.Key_Tab and isinstance(single, NodeItem):
            self.edit_inline(scene.add_next(single))
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = 1.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else GRID
            dx = {Qt.Key.Key_Left: -step, Qt.Key.Key_Right: step}.get(Qt.Key(key), 0.0)
            dy = {Qt.Key.Key_Up: -step, Qt.Key.Key_Down: step}.get(Qt.Key(key), 0.0)
            scene.nudge(dx, dy)
        else:
            super().keyPressEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:
        return False  # Tab adds a box instead of moving the focus

    # Inline label editing
    def edit_inline(self, item: NodeItem | EdgeItem) -> None:
        self.finish_inline(True)
        viewport = self.viewport()
        assert viewport is not None
        editor = QLineEdit(viewport)
        editor.setObjectName("diagramInline")
        if isinstance(item, NodeItem):
            editor.setText(item.node.label)
            rect = self.mapFromScene(item.mapRectToScene(item.body())).boundingRect()
            width = max(140, rect.width() - 8)
            center = rect.center()
        else:
            editor.setText(item.edge.label)
            center = self.mapFromScene(item.label_point())
            width = 160
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor.setFixedWidth(width)
        editor.move(center.x() - width // 2, center.y() - editor.sizeHint().height() // 2)
        editor.selectAll()
        editor.returnPressed.connect(lambda: self.finish_inline(True))
        editor.editingFinished.connect(lambda: self.finish_inline(True))
        editor.installEventFilter(self)
        self.editor = editor
        self._editing = item
        editor.show()
        editor.setFocus()

    def finish_inline(self, keep: bool) -> None:
        editor, item = self.editor, self._editing
        if editor is None or item is None:
            return
        self.editor = None
        self._editing = None
        text = editor.text().strip()
        editor.hide()
        editor.deleteLater()
        if keep and not sip.isdeleted(item) and item.scene() is self.scene():
            if isinstance(item, NodeItem) and not text:
                text = item.node.label  # a box keeps a name
            self.diagram().set_label(item, text)
        self.setFocus()

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        if (
            watched is self.editor
            and event is not None
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
        ):
            if event.key() == Qt.Key.Key_Escape:
                self.finish_inline(False)
                return True
            if event.key() == Qt.Key.Key_Tab and isinstance(self._editing, NodeItem):
                item = self._editing
                self.finish_inline(True)
                self.edit_inline(self.diagram().add_next(item))
                return True
        return super().eventFilter(watched, event)


# The window ------------------------------------------------------------------------------


class DiagramDialog:
    """Canvas on the left; on the right the selected box or arrow and the code."""

    def __init__(self, api: ForgeAPI, chart: fc.Flowchart, updating: bool) -> None:
        self.api = api
        theme = api.theme
        self.dialog = api.framed_dialog(tr("Diagram"), resizable=True)
        self.DialogCode = self.dialog.DialogCode
        self.scene = DiagramScene(chart, theme, self.dialog)
        self.view = DiagramView(self.scene, self._add_at)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Toolbar: add shapes; undo, layout, direction, delete.
        bar = QHBoxLayout()
        bar.setSpacing(4)
        for shape, icon in (("rect", "square"), ("round", "square"), ("diamond", "diamond"),
                            ("circle", "circle"), ("database", "file-spreadsheet")):  # fmt: skip
            button = QToolButton(body)
            button.setObjectName("docToolButton")
            button.setText(_shape_names()[shape])
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setIcon(api.icon(icon))
            button.setToolTip(tr("Add: {shape}", shape=_shape_names()[shape]))
            button.clicked.connect(lambda _c=False, s=shape: self._add_shape(s))
            bar.addWidget(button)
        bar.addStretch(1)
        undo = QToolButton(body)
        undo.setObjectName("docToolButton")
        undo.setIcon(api.icon("undo-2"))
        undo.setToolTip(tr("Undo"))
        undo.clicked.connect(self.scene.undo)
        bar.addWidget(undo)
        bar.addSpacing(8)
        self.direction = QComboBox(body)
        for code, name in _direction_names().items():
            self.direction.addItem(name, code)
        self.direction.setCurrentIndex(max(0, self.direction.findData(chart.direction)))
        self.direction.currentIndexChanged.connect(self._direction_changed)
        tidy = QPushButton(tr("Tidy Up"), body)
        tidy.setToolTip(tr("Place the boxes in layers along the flow"))
        tidy.clicked.connect(self.scene.relayout)
        delete = QPushButton(tr("Delete"), body)
        delete.clicked.connect(self.scene.delete_selected)
        bar.addWidget(QLabel(tr("Direction"), body))
        bar.addWidget(self.direction)
        bar.addWidget(tidy)
        bar.addWidget(delete)
        layout.addLayout(bar)

        # Side panel.
        side = QWidget(body)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.label = QLineEdit(side)
        self.kind = QComboBox(side)
        form.addRow(tr("Text"), self.label)
        form.addRow(tr("Kind"), self.kind)
        self.selection_note = QLabel(tr("Select a box or an arrow to change it."), side)
        self.selection_note.setObjectName("resultNote")
        self.selection_note.setWordWrap(True)
        self.code = QPlainTextEdit(side)
        self.code.setReadOnly(True)
        self.code.setFont(code_font())
        self.code.setObjectName("diagramCode")
        code_title = QLabel(tr("Mermaid code"), side)
        code_title.setObjectName("cronSection")
        side_layout.addWidget(self.selection_note)
        side_layout.addLayout(form)
        side_layout.addSpacing(6)
        side_layout.addWidget(code_title)
        side_layout.addWidget(self.code, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal, body)
        splitter.addWidget(self.view)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self.hint = InfoHint(api.icon("info"), body)
        self.hint.set_text(
            tr(
                "Point at a box and drag one of its round connectors onto another box to "
                "connect them, or onto empty canvas to add a connected box. Drag the "
                "handles of a selected box to resize it. Double-click or Enter edits a "
                "label, Tab adds the next step, Delete removes, Ctrl+Z undoes."
            )
        )
        bottom.addWidget(self.hint, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, body
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Update Diagram") if updating else tr("Insert Diagram"))
            ok.setAutoDefault(False)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel is not None:
            cancel.setAutoDefault(False)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.dialog.reject)
        bottom.addWidget(buttons)
        layout.addLayout(bottom)

        for sequence, slot in (
            (QKeySequence.StandardKey.Undo, self.scene.undo),
            (QKeySequence.StandardKey.Redo, self.scene.redo),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self.view)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)

        self._timer = QTimer(self.dialog)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._refresh_code)
        self.scene.changed_chart.connect(self._timer.start)
        self.scene.selectionChanged.connect(self._selection_changed)
        self.scene.edit_requested.connect(self.view.edit_inline)
        self.scene.rebuilt.connect(self._rebuilt)
        self.label.textEdited.connect(self._label_edited)
        self.label.editingFinished.connect(self.scene.commit)
        self.kind.activated.connect(self._kind_chosen)
        self._selection_changed()
        self._refresh_code()
        self.dialog.resize(1100, 680)
        QTimer.singleShot(0, self._fit)

    # Helpers
    def _fit(self) -> None:
        rect = self.scene.itemsBoundingRect().adjusted(-80, -80, 80, 80)
        self.scene.setSceneRect(
            rect.united(QRectF(-400, -300, 800, 600)).adjusted(-600, -600, 600, 600)
        )
        self.view.centerOn(rect.center())
        self.view.setFocus()

    def _accept(self) -> None:
        self.view.finish_inline(True)
        self.dialog.accept()

    def _add_at(self, at: QPointF) -> None:
        self.view.edit_inline(self.scene.add_node("rect", at))

    def _add_shape(self, shape: str) -> None:
        """Add a box: after the selected box (connected), else in the middle."""
        selected = self._selected()
        if isinstance(selected, NodeItem):
            item = self.scene.add_next(selected)
            item.node.shape = shape
            item.prepareGeometryChange()
            item.update()
            self.scene.commit()
        else:
            viewport = self.view.viewport()
            assert viewport is not None
            center = self.view.mapToScene(viewport.rect().center())
            offset = 20 * (len(self.scene.chart.nodes) % 6)
            item = self.scene.add_node(shape, center + QPointF(offset, offset))
        self.view.edit_inline(item)

    def _selected(self) -> NodeItem | EdgeItem | None:
        if sip.isdeleted(self.scene) or sip.isdeleted(self.label):  # window closing
            return None
        items = self.scene.selectedItems()
        if len(items) != 1:
            return None
        item = items[0]
        return item if isinstance(item, NodeItem | EdgeItem) else None

    def _selection_changed(self) -> None:
        if sip.isdeleted(self.kind):
            return
        item = self._selected()
        self.kind.clear()
        if isinstance(item, NodeItem):
            for code, name in _shape_names().items():
                self.kind.addItem(name, code)
            self.kind.setCurrentIndex(self.kind.findData(item.node.shape))
            self.label.setText(item.node.label)
        elif isinstance(item, EdgeItem):
            for code, name in _edge_names().items():
                self.kind.addItem(name, code)
            self.kind.setCurrentIndex(self.kind.findData(item.edge.style))
            self.label.setText(item.edge.label)
        else:
            self.label.clear()
        for widget in (self.label, self.kind):
            widget.setEnabled(item is not None)
        self.selection_note.setVisible(item is None)

    def _label_edited(self, text: str) -> None:
        item = self._selected()
        if isinstance(item, NodeItem):
            item.prepareGeometryChange()
            item.node.label = text
            for edge in item.edges:
                edge.update_path()
            item.update()
        elif isinstance(item, EdgeItem):
            item.prepareGeometryChange()
            item.edge.label = text
            item.update()
        self._timer.start()

    def _kind_chosen(self, _index: int) -> None:
        item = self._selected()
        value = str(self.kind.currentData())
        if isinstance(item, NodeItem):
            item.prepareGeometryChange()
            item.node.shape = value
            for edge in item.edges:
                edge.update_path()
            item.update()
        elif isinstance(item, EdgeItem):
            item.edge.style = value
            item.update()
        self.scene.commit()

    def _direction_changed(self) -> None:
        self.scene.chart.direction = str(self.direction.currentData())
        self.scene.commit()

    def _rebuilt(self) -> None:
        self.direction.blockSignals(True)
        self.direction.setCurrentIndex(max(0, self.direction.findData(self.scene.chart.direction)))
        self.direction.blockSignals(False)
        self._selection_changed()

    def _refresh_code(self) -> None:
        if not sip.isdeleted(self.code):
            self.code.setPlainText(fc.to_mermaid(self.scene.chart))

    def exec(self) -> int:
        return self.dialog.exec()


def open_diagram_editor(api: ForgeAPI, editor: EditorHandle) -> None:
    lines = editor.text().splitlines()
    caret_line = editor.selected_line_range()[0]
    block = fc.block_at(lines, caret_line)
    chart: fc.Flowchart
    if block is not None:
        first, last = block
        try:
            chart = fc.parse("\n".join(lines[first + 1 : last]))
        except fc.FlowchartError as exc:
            api.inform(
                tr("Diagram"),
                tr(
                    "Forge can only draw flowcharts ({reason}). Edit this diagram as text; "
                    "the preview shows the result.",
                    reason=str(exc),
                ),
            )
            return
    else:
        chart = fc.Flowchart(
            "TD",
            [
                fc.Node("A", tr("Start"), "stadium", 0, 0),
                fc.Node("B", tr("Next step"), "rect", 0, 130),
            ],
            [fc.Edge("A", "B")],
        )
    dialog = DiagramDialog(api, chart, block is not None)
    if dialog.exec() != dialog.DialogCode.Accepted:
        return
    eol = editor.eol
    code = fc.to_mermaid(dialog.scene.chart).rstrip("\n").split("\n")
    fenced = ["```mermaid", *code, "```"]
    if block is not None:
        editor.replace_lines(block[0], block[1], fenced)
    else:
        editor.insert(eol + eol.join(fenced) + eol)
    api.status(tr("Diagram updated.") if block is not None else tr("Diagram inserted."))

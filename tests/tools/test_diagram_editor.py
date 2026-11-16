"""The flowchart drawing window: connecting, resizing, inline editing, undo."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.tools.markdown_tool import flowchart as fc
from forge.tools.markdown_tool.diagram import DiagramDialog, EdgeItem, NodeItem
from forge.ui.main_window import MainWindow


def make_dialog(qtbot: QtBot) -> DiagramDialog:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    chart = fc.parse("flowchart TD\n  A[Start] --> B[End]\n")
    dialog = DiagramDialog(window.extension_host.api("forge.markdown"), chart, True)
    dialog.dialog.show()
    qtbot.waitExposed(dialog.dialog)
    return dialog


def test_dropping_a_link_on_a_box_connects_and_on_empty_canvas_adds_a_box(qtbot: QtBot) -> None:
    dialog = make_dialog(qtbot)
    scene = dialog.scene
    a, b = scene.nodes["A"], scene.nodes["B"]
    scene.start_link(b, b.scenePos())
    scene.drag_link(a.scenePos())
    assert a.target  # highlighted as the drop target
    scene.finish_link(a.scenePos() + QPointF(20, 5))  # anywhere on the box
    assert any(e.source == "B" and e.target == "A" for e in scene.chart.edges)
    assert not a.target

    scene.start_link(b, b.scenePos())
    new = scene.finish_link(b.scenePos() + QPointF(300, 0))
    assert isinstance(new, NodeItem)
    assert any(e.source == "B" and e.target == new.node.id for e in scene.chart.edges)
    assert dialog.view.editor is not None  # its label is being edited
    dialog.view.editor.setText("Archive")
    dialog.view.finish_inline(True)
    assert new.node.label == "Archive"

    scene.start_link(b, b.scenePos())
    assert scene.finish_link(b.scenePos() + QPointF(0, 30)) is None  # too close: nothing
    dialog.dialog.close()


def test_resize_with_a_handle_and_undo_redo(qtbot: QtBot) -> None:
    dialog = make_dialog(qtbot)
    scene = dialog.scene
    a = scene.nodes["A"]
    a.setSelected(True)
    body = a.mapRectToScene(a.body())
    view = dialog.view
    corner = view.mapFromScene(body.bottomRight())
    assert a.handle_at(a.mapFromScene(body.bottomRight())) == "br"
    viewport = view.viewport()
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=corner)
    target = view.mapFromScene(body.bottomRight() + QPointF(80, 40))
    qtbot.mouseMove(viewport, pos=target)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=target)
    width, height = a.size()
    assert width >= body.width() + 60 and height >= body.height() + 30
    assert "forge-layout" in fc.to_mermaid(scene.chart) and a.node.w == width

    scene.undo()
    a = scene.nodes["A"]
    assert (a.node.w, a.node.h) == (0, 0)
    scene.redo()
    assert scene.nodes["A"].node.w == width
    dialog.dialog.close()


def test_tab_adds_the_next_step_along_the_flow(qtbot: QtBot) -> None:
    dialog = make_dialog(qtbot)
    scene = dialog.scene
    b = scene.nodes["B"]
    scene.clearSelection()
    b.setSelected(True)
    dialog.view.setFocus()
    qtbot.keyClick(dialog.view, Qt.Key.Key_Tab)
    assert len(scene.chart.nodes) == 3
    new = next(n for n in scene.nodes.values() if n.node.id not in ("A", "B"))
    assert new.pos().y() > b.pos().y()  # below, as the flow goes top to bottom
    assert any(e.source == "B" and e.target == new.node.id for e in scene.chart.edges)
    assert dialog.view.editor is not None
    qtbot.keyClick(dialog.view.editor, Qt.Key.Key_Escape)
    assert dialog.view.editor is None

    edge = next(i for i in scene.items() if isinstance(i, EdgeItem))
    dialog.view.edit_inline(edge)
    assert dialog.view.editor is not None
    dialog.view.editor.setText("yes")
    dialog.view.finish_inline(True)
    assert edge.edge.label == "yes"
    count = len(scene.undo_stack)
    scene.undo()
    assert len(scene.undo_stack) == count - 1
    dialog.dialog.close()

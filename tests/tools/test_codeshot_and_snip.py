"""Code shot and the snipping tool (capture is faked: tests never read the screen)."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from forge.core.settings import Settings
from forge.ui.main_window import MainWindow


def make_window(qtbot: QtBot) -> MainWindow:
    window = MainWindow(Settings())
    qtbot.addWidget(window)
    return window


def test_code_shot_collects_colors_and_renders(qtbot: QtBot) -> None:
    from forge.editor.lexers import language_by_id
    from forge.tools.utilities import codeshot

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    window.set_document_language(language_by_id("python"))
    tab.setText("\n    def f(x):\n        return x  # done\n\n")
    lines, skipped = codeshot.trim_blank(codeshot.collect(tab, 0, 4, window.theme))
    assert skipped == 1 and len(lines) == 2
    assert "".join(run[0] for run in lines[0]) == "def f(x):"  # common indent removed
    assert "".join(run[0] for run in lines[1]) == "    return x  # done"
    assert len({run[1].name() for run in lines[0]}) > 1  # keyword and name differ
    image = codeshot.render(lines, window.theme, codeshot.Options(title="f.py"))
    plain = codeshot.render(
        lines, window.theme, codeshot.Options(frame=False, backdrop="none", line_numbers=False)
    )
    assert image.width() > plain.width() and image.height() > plain.height()
    assert plain.pixelColor(0, 0) == QColor(window.theme.editor_bg)
    assert image.devicePixelRatio() == codeshot.SCALE


def test_code_shot_command_copies_the_image(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from forge.tools.utilities import codeshot

    window = make_window(qtbot)
    tab = window.current_tab()
    assert tab is not None
    tab.setText("a = 1\nb = 2\nc = 3\n")
    seen: list[codeshot.CodeShot] = []
    opened: list[object] = []
    monkeypatch.setattr(codeshot.CodeShot, "__init__", lambda *a: opened.append(a))
    window.extension_host.run_command("utilities.codeshot")  # nothing selected
    assert opened == []  # no window, only a note
    monkeypatch.undo()
    tab.setSelection(1, 0, 2, 3)

    def accept(self: codeshot.CodeShot) -> int:
        seen.append(self)
        assert self.options.first_number == 2
        self.numbers.setChecked(False)
        self.copy()
        return 1

    monkeypatch.setattr(codeshot.CodeShot, "exec", accept)
    window.extension_host.run_command("utilities.codeshot")
    clipboard = QApplication.clipboard()
    assert clipboard is not None and seen
    assert not clipboard.image().isNull()
    assert clipboard.image().size() == seen[0].image.size()


def test_crop_uses_physical_pixels() -> None:
    from forge.tools.utilities.snipping import crop

    shot = QPixmap(400, 300)
    shot.fill(QColor(10, 20, 30))
    shot.setDevicePixelRatio(2)
    part = crop(shot, QRect(10, 10, 50, 40))
    assert part.size().width() == 100 and part.size().height() == 80
    assert part.devicePixelRatio() == 2


def test_region_overlay_returns_the_dragged_area(qtbot: QtBot) -> None:
    from forge.tools.utilities.snipping import RegionOverlay

    app = QApplication.instance()
    screen = app.primaryScreen()  # type: ignore[union-attr]
    shot = QPixmap(screen.geometry().size())
    shot.fill(QColor(200, 0, 0))
    overlay = RegionOverlay(shot, screen)  # deletes itself on close
    chosen: list[QPixmap] = []
    overlay.chosen.connect(chosen.append)
    overlay.show()
    qtbot.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QRect(20, 20, 1, 1).topLeft())
    qtbot.mouseMove(overlay, pos=QRect(120, 70, 1, 1).topLeft())
    overlay._end = QRect(120, 70, 1, 1).topLeft()  # offscreen mouse moves need no button state
    qtbot.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QRect(120, 70, 1, 1).topLeft())
    assert len(chosen) == 1 and chosen[0].width() == 100 and chosen[0].height() == 50


def test_annotator_draws_undoes_and_copies(qtbot: QtBot) -> None:
    from forge.tools.utilities.annotate import Annotator, ArrowItem

    window = make_window(qtbot)
    api = window.extension_host.api("forge.utilities")
    shot = QPixmap(200, 120)
    shot.fill(QColor(255, 255, 255))
    annotator = Annotator(api, shot)
    annotator.set_color(QColor(255, 0, 0))
    for tool, end in (("rect", (60, 50)), ("arrow", (150, 100)), ("pen", (80, 90))):
        annotator.tool = tool
        item = annotator.begin_shape(QPointF(10, 10))
        annotator.drag_shape(item, QPointF(10, 10), QPointF(*end), False)
        annotator.finish_shape(item)
    assert len(annotator.items) == 3
    assert isinstance(annotator.items[1], ArrowItem)
    annotator.tool = "line"  # a click without a drag adds nothing
    item = annotator.begin_shape(QPointF(5, 5))
    annotator.finish_shape(item)
    assert len(annotator.items) == 3
    annotator.undo()
    assert len(annotator.items) == 2
    annotator.copy()
    image: QImage = QApplication.clipboard().image()  # type: ignore[union-attr]
    assert image.size() == shot.size()
    assert image.pixelColor(10, 30).red() > 200 and image.pixelColor(10, 30).green() < 80
    assert image.pixelColor(190, 10) == QColor(255, 255, 255)


def test_snipper_full_screen_goes_to_the_annotator(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.tools.utilities import capture, snipping
    from forge.tools.utilities.annotate import Annotator

    window = make_window(qtbot)
    fake = QPixmap(64, 48)
    fake.fill(QColor(0, 128, 0))
    monkeypatch.setattr(capture, "grab", lambda _screen: fake)
    monkeypatch.setattr(capture, "is_wayland", lambda: False)
    monkeypatch.setattr(capture, "mac_capture_allowed", lambda ask=True: True)
    opened: list[QPixmap] = []
    monkeypatch.setattr(Annotator, "exec", lambda self: opened.append(self.shot) or 0)
    monkeypatch.setattr(snipping, "ask_options", lambda _api: snipping.SnipOptions(False, 0, False))
    window.extension_host.run_command("utilities.snip")
    qtbot.waitUntil(lambda: bool(opened), timeout=2000)
    assert opened[0].size() == fake.size()


def _drawn(annotator: object, tool: str, start: tuple[float, float], end: tuple[float, float]):  # type: ignore[no-untyped-def]
    annotator.tool = tool  # type: ignore[attr-defined]
    item = annotator.begin_shape(QPointF(*start))  # type: ignore[attr-defined]
    annotator.drag_shape(item, QPointF(*start), QPointF(*end), False)  # type: ignore[attr-defined]
    annotator.finish_shape(item)  # type: ignore[attr-defined]
    return item


def test_annotator_resize_move_and_undo(qtbot: QtBot) -> None:
    from forge.tools.utilities.annotate import (
        Annotator,
        capture_state,
        frame_of,
        handles_of,
        resize_item,
    )

    window = make_window(qtbot)
    shot = QPixmap(300, 200)
    shot.fill(QColor(255, 255, 255))
    annotator = Annotator(window.extension_host.api("forge.utilities"), shot)
    box = _drawn(annotator, "rect", (10, 10), (60, 40))
    arrow = _drawn(annotator, "arrow", (100, 100), (150, 150))
    stroke = _drawn(annotator, "pen", (200, 20), (240, 60))

    before = {box: capture_state(box)}
    resize_item(box, before[box], "br", QPointF(110, 90))
    assert frame_of(box).bottomRight() == QPointF(110, 90)
    annotator.record_changes(before)

    names = [name for name, _point in handles_of(arrow)]
    assert names == ["p1", "p2"]
    before = {arrow: capture_state(arrow)}
    resize_item(arrow, before[arrow], "p2", QPointF(180, 120))
    assert arrow.mapToScene(arrow.line.p2()) == QPointF(180, 120)  # type: ignore[attr-defined]
    annotator.record_changes(before)

    before = {stroke: capture_state(stroke)}
    old = frame_of(stroke)
    resize_item(stroke, before[stroke], "r", QPointF(old.right() + old.width(), 0))
    assert abs(frame_of(stroke).width() - old.width() * 2) < old.width() * 0.2
    annotator.record_changes(before)

    before = {box: capture_state(box)}
    box.setPos(QPointF(5, 5))
    annotator.record_changes(before)
    annotator.record_changes({box: capture_state(box)})  # nothing changed: no step

    annotator.undo()  # the move
    assert box.pos() == QPointF(0, 0)
    annotator.undo()  # the stroke resize
    assert frame_of(stroke) == old
    annotator.undo()  # the arrow
    assert arrow.mapToScene(arrow.line.p2()) == QPointF(150, 150)  # type: ignore[attr-defined]
    annotator.undo()  # the box resize
    assert frame_of(box).bottomRight() == QPointF(60, 40)


def test_annotator_crop_erase_and_selection_color(qtbot: QtBot) -> None:
    from forge.tools.utilities.annotate import Annotator

    window = make_window(qtbot)
    shot = QPixmap(400, 300)
    shot.fill(QColor(255, 255, 255))
    shot.setDevicePixelRatio(2)  # 200 x 150 points
    annotator = Annotator(window.extension_host.api("forge.utilities"), shot)
    box = _drawn(annotator, "rect", (10, 10), (50, 50))
    line = _drawn(annotator, "line", (100, 100), (150, 100))

    annotator.set_tool("select")
    box.setSelected(True)
    annotator.set_color(QColor(0, 0, 255))
    assert box.pen().color() == QColor(0, 0, 255)  # type: ignore[attr-defined]
    annotator.undo()
    assert box.pen().color() != QColor(0, 0, 255)  # type: ignore[attr-defined]

    annotator.set_tool("eraser")
    annotator.erase_at(QPointF(125, 100))
    assert line not in annotator.items and line.scene() is None
    annotator.undo()
    assert line in annotator.items and line.scene() is annotator.scene

    annotator.set_tool("crop")
    assert annotator.scene.sceneRect() == annotator.full  # the whole picture to choose from
    full = QRectF(annotator.full)
    annotator.drag_crop(full, "br", full.bottomRight(), QPointF(100, 60))
    assert annotator.pending_crop == QRectF(0, 0, 100, 60)
    annotator.drag_crop(QRectF(annotator.pending_crop), "move", QPointF(50, 30), QPointF(500, 30))
    assert annotator.pending_crop == QRectF(100, 0, 100, 60)  # stops at the edge
    annotator.drag_crop(QRectF(annotator.pending_crop), "new", QPointF(0, 0), QPointF(100, 60))
    annotator.set_tool("select")  # leaving the crop tool applies it
    assert annotator.scene.sceneRect() == QRectF(0, 0, 100, 60)
    image = annotator.render()
    assert (image.width(), image.height()) == (200, 120)  # physical pixels
    assert image.pixelColor(20, 20).red() > 150  # the box edge at (10, 10)
    annotator.undo()
    assert annotator.render().width() == 400


def test_mac_area_capture_reports_a_missing_tool(qtbot: QtBot) -> None:
    import sys

    from PyQt6.QtCore import QObject

    from forge.tools.utilities.capture import MacAreaCapture

    if sys.platform == "darwin":
        pytest.skip("would open the real crosshair")
    parent = QObject()
    results: list[tuple[object, str]] = []
    MacAreaCapture(lambda pixmap, error: results.append((pixmap, error)), 2.0, parent).start()
    qtbot.waitUntil(lambda: bool(results), timeout=3000)
    assert results[0][0] is None and "screencapture" in results[0][1]


def test_snip_now_skips_the_options_and_returns_to_minimized(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge.tools.utilities import capture, snipping
    from forge.tools.utilities.annotate import Annotator

    window = make_window(qtbot)
    window.show()
    window.showMinimized()
    fake = QPixmap(40, 30)
    fake.fill(QColor(9, 9, 9))
    monkeypatch.setattr(capture, "grab", lambda _screen: fake)
    monkeypatch.setattr(capture, "is_wayland", lambda: False)
    monkeypatch.setattr(capture, "mac_capture_allowed", lambda ask=True: True)
    monkeypatch.setattr(snipping, "ask_options", lambda _api: pytest.fail("no options window"))
    opened: list[bool] = []
    monkeypatch.setattr(Annotator, "exec", lambda self: opened.append(True) or 0)
    api = window.extension_host.api("forge.utilities")
    api.set_setting("snip_area", False)  # last time: full screen
    window.extension_host.call("forge.utilities", "forge.tools.utilities.actions:snip_now")
    second = snipping.snip_now(api)  # a second press while busy does nothing
    assert snipping.Snipper.running is not second
    qtbot.waitUntil(lambda: bool(opened), timeout=3000)
    assert len(opened) == 1
    qtbot.waitUntil(lambda: window.isMinimized(), timeout=2000)
    assert snipping.Snipper.running is None


def test_preferences_store_the_global_snip_shortcut(qtbot: QtBot) -> None:
    from PyQt6.QtGui import QKeySequence

    from forge.ui.preferences import PreferencesDialog

    window = make_window(qtbot)
    seen: list[str] = []
    window.extension_events.subscribe("settings_changed", lambda: seen.append("x"), "test")
    dialog = PreferencesDialog(window.settings, window.apply_settings, window)
    qtbot.addWidget(dialog)
    dialog.snip_key.setKeySequence(QKeySequence("Ctrl+Shift+F9"))
    dialog.global_snip.setChecked(False)  # applies live, like every preference
    assert seen
    snip = window.settings.tools["forge.utilities"]
    assert snip["global_snip"] is False and snip["global_snip_key"] == "Ctrl+Shift+F9"


def test_annotation_window_is_brought_forward(qtbot: QtBot) -> None:
    from forge.tools.utilities.annotate import BRING_FORWARD_MS, Annotator

    window = make_window(qtbot)
    shot = QPixmap(60, 40)
    shot.fill(QColor(1, 2, 3))
    annotator = Annotator(window.extension_host.api("forge.utilities"), shot)
    raised: list[int] = []
    annotator.dialog.exec = lambda: 0  # type: ignore[method-assign]
    annotator.dialog.raise_ = lambda: raised.append(1)  # type: ignore[method-assign]
    annotator.exec()
    qtbot.waitUntil(lambda: len(raised) == len(BRING_FORWARD_MS), timeout=3000)
    annotator.dialog.close()

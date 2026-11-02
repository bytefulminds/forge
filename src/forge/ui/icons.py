"""Bundled Lucide icons (ISC, see resources/icons/lucide/LICENSE.txt), tinted per theme."""

from __future__ import annotations

from functools import cache
from importlib import resources

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

ICON_SIZE = 16


@cache
def _source(name: str) -> str:
    package = resources.files("forge.resources.icons").joinpath("lucide")
    return package.joinpath(f"{name}.svg").read_text(encoding="utf-8")


def _pixmap(name: str, color: str, size: int) -> QPixmap:
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if isinstance(app, QGuiApplication) else 1.0
    scale = max(2.0, ratio)  # render sharp on Retina and when scaled
    svg = _source(name).replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(round(size * scale), round(size * scale))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pixmap.width(), pixmap.height()))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


@cache
def status_pixmap(name: str, color: str, size: int) -> QPixmap:
    """A small state icon: a Lucide icon, or ``"dot"`` for a filled circle."""
    if name != "dot":
        return _pixmap(name, color, size)
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if isinstance(app, QGuiApplication) else 1.0
    scale = max(2.0, ratio)
    pixmap = QPixmap(round(size * scale), round(size * scale))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    diameter = pixmap.width() * 0.62
    offset = (pixmap.width() - diameter) / 2
    painter.drawEllipse(QRectF(offset, offset, diameter, diameter))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


@cache
def themed_icon(name: str, normal: str, active: str, disabled: str) -> QIcon:
    """An icon drawn in ``normal``, ``active`` (hover, checked) and ``disabled`` colors."""
    icon = QIcon()
    off, on = QIcon.State.Off, QIcon.State.On
    for mode, color in (
        (QIcon.Mode.Normal, normal),
        (QIcon.Mode.Active, active),
        (QIcon.Mode.Selected, active),
        (QIcon.Mode.Disabled, disabled),
    ):
        icon.addPixmap(_pixmap(name, color, ICON_SIZE), mode, off)
    icon.addPixmap(_pixmap(name, active, ICON_SIZE), QIcon.Mode.Normal, on)
    icon.addPixmap(_pixmap(name, active, ICON_SIZE), QIcon.Mode.Active, on)
    return icon

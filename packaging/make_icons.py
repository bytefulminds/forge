"""Render Forge's app icons from the logo SVG, for the packaged builds.

    uv run python packaging/make_icons.py build/icons

Writes, from ``src/forge/resources/icons/forge.svg``:

- ``forge.icns``  macOS app icon (PNG entries, 16 to 1024 px), with Apple's
  margin around the tile so it sits well among other Dock icons;
- ``forge.ico``   Windows icon (PNG entries, 16 to 256 px);
- ``hicolor/<n>x<n>/apps/<app id>.png``  Linux icon theme sizes;
- ``forge-512.png``  for the AppImage's top-level icon.

The ICNS and ICO containers are written here (they are simple formats), so
the script needs nothing but PyQt6 and runs the same on every platform.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "src" / "forge" / "resources" / "icons" / "forge.svg"
APP_ID = "nl.bytefulminds.Forge"

# forge.svg draws a 224 px tile on a 256 px canvas; Apple's grid puts an
# 824 px tile on a 1024 px canvas.
_SVG_TILE = 224 / 256
_MAC_TILE = 824 / 1024

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
HICOLOR_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
# ICNS entry types holding PNG data, by pixel size.
ICNS_TYPES = (
    (b"icp4", 16),
    (b"icp5", 32),
    (b"ic11", 32),  # 16 @2x
    (b"icp6", 64),
    (b"ic12", 64),  # 32 @2x
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic13", 256),  # 128 @2x
    (b"ic09", 512),
    (b"ic14", 512),  # 256 @2x
    (b"ic10", 1024),  # 512 @2x
)


def render_png(size: int, tile: float = _SVG_TILE) -> bytes:
    """The logo as a ``size`` px PNG, its tile taking ``tile`` of the width."""
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
    from PyQt6.QtGui import QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        raise RuntimeError(f"Cannot read {SVG}")
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    canvas = size * tile / _SVG_TILE
    offset = (size - canvas) / 2
    renderer.render(painter, QRectF(offset, offset, canvas, canvas))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError("PNG encoding failed")
    buffer.close()
    return bytes(data.data())


def ico_bytes(images: dict[int, bytes]) -> bytes:
    """An ICO file with one PNG entry per size (Windows Vista and later)."""
    sizes = sorted(images)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    payload = b""
    for size in sizes:
        png = images[size]
        side = 0 if size >= 256 else size  # 0 means 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        payload += png
        offset += len(png)
    return header + entries + payload


def icns_bytes(images: dict[int, bytes]) -> bytes:
    """An ICNS file with PNG entries (macOS 10.7 and later)."""
    body = b""
    for kind, size in ICNS_TYPES:
        png = images[size]
        body += kind + struct.pack(">I", 8 + len(png)) + png
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: make_icons.py OUTPUT_DIR", file=sys.stderr)
        return 2
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtGui import QGuiApplication

    app = QGuiApplication(["make_icons"])  # noqa: F841  (needed to paint)

    plain = {size: render_png(size) for size in {*ICO_SIZES, *HICOLOR_SIZES}}
    mac = {size: render_png(size, _MAC_TILE) for _, size in ICNS_TYPES}

    (out / "forge.ico").write_bytes(ico_bytes({s: plain[s] for s in ICO_SIZES}))
    (out / "forge.icns").write_bytes(icns_bytes(mac))
    for size in HICOLOR_SIZES:
        folder = out / "hicolor" / f"{size}x{size}" / "apps"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{APP_ID}.png").write_bytes(plain[size])
    (out / "forge-512.png").write_bytes(plain[512])
    print(f"Icons written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

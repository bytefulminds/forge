from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QMainWindow
from pytestqt.qtbot import QtBot

from forge.ui import window_buttons as wb
from forge.ui.title_bar import TitleBar


def test_platform_layouts() -> None:
    assert wb.detect("darwin") == wb.MAC
    assert wb.detect("win32") == wb.DEFAULT
    assert wb.DEFAULT.right == ("minimize", "maximize", "close")


def test_gnome_layouts() -> None:
    assert wb.parse_gnome("'appmenu:close'\n") == wb.ButtonLayout((), ("close",))
    assert wb.parse_gnome("'close,minimize,maximize:'") == wb.ButtonLayout(
        ("close", "minimize", "maximize"), ()
    )
    assert wb.parse_gnome("icon:") is None
    layout = wb.detect("linux", {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, Path("/x"),
                       gsettings=lambda: "'close,maximize,minimize:appmenu'")  # fmt: skip
    assert layout.left == ("close", "maximize", "minimize")
    fallback = wb.detect("linux", {}, Path("/nonexistent"), gsettings=lambda: None)
    assert fallback == wb.DEFAULT


def test_gtk_settings_file_and_kde(tmp_path: Path) -> None:
    gtk = tmp_path / ".config" / "gtk-3.0"
    gtk.mkdir(parents=True)
    (gtk / "settings.ini").write_text("[Settings]\ngtk-decoration-layout=close:\n")
    assert wb.detect("linux", {}, tmp_path, gsettings=lambda: None).left == ("close",)
    (tmp_path / ".config" / "kwinrc").write_text(
        "[org.kde.kdecoration2]\nButtonsOnLeft=XIA\nButtonsOnRight=\n"
    )
    kde = wb.detect("linux", {"XDG_CURRENT_DESKTOP": "KDE"}, tmp_path)
    assert kde == wb.ButtonLayout(("close", "minimize", "maximize"), ())
    stock = wb.detect("linux", {"XDG_CURRENT_DESKTOP": "KDE"}, tmp_path / "none")
    assert stock.right == ("minimize", "maximize", "close")


def _icon() -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill()
    return QIcon(pixmap)


def test_title_bar_follows_the_layout(qtbot: QtBot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)
    mac = TitleBar(window, _icon(), layout_spec=wb.MAC)
    assert list(mac.left_group.buttons) == ["close", "minimize", "maximize"]
    assert not mac.right_group.buttons and mac.icon.isHidden()
    assert mac.max_button is not None and mac.max_button.toolTip() == "Enter Full Screen"

    windows = TitleBar(window, _icon(), layout_spec=wb.DEFAULT)
    assert list(windows.right_group.buttons) == ["minimize", "maximize", "close"]
    assert not windows.icon.isHidden()

    gnome = TitleBar(window, _icon(), layout_spec=wb.ButtonLayout((), ("close",)))
    assert gnome.min_button is None and gnome.close_button is not None

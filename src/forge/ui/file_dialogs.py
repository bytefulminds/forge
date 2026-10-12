"""Open, Save As and folder dialogs.

By default these are Qt's own file dialog inside a Forge frame, styled like
the rest of Forge. With "Use the system file dialogs" (Preferences) Forge
uses the native dialogs instead (Finder on macOS, GTK or KDE on Linux).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QFileInfo, QSize, QStandardPaths, Qt, QUrl
from PyQt6.QtGui import QAbstractFileIconProvider, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFileIconProvider,
    QHeaderView,
    QSplitter,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from forge.themes.theme import Theme
from forge.ui.framed_dialog import FramedDialog
from forge.ui.icons import ICON_SIZE, themed_icon

# Set by the main window from the settings and the active theme.
use_native_dialogs = False
current_theme: Theme | None = None

_TOOL_ICONS = {
    "backButton": "arrow-left",
    "forwardButton": "arrow-right",
    "toParentButton": "arrow-up",
    "newFolderButton": "folder-plus",
    "listModeButton": "layout-grid",
    "detailModeButton": "list",
}


class _IconProvider(QFileIconProvider):
    """Lucide folder and file icons in the theme's colors."""

    def __init__(self, theme: Theme) -> None:
        super().__init__()
        self._folder = themed_icon("folder", theme.accent, theme.accent, theme.text_disabled)
        self._file = themed_icon("file", theme.text_muted, theme.text, theme.text_disabled)
        self._drive = themed_icon("hard-drive", theme.text_muted, theme.text, theme.text_disabled)

    def icon(self, what: object) -> QIcon:
        if isinstance(what, QFileInfo):
            if what.isRoot():
                return self._drive
            return self._folder if what.isDir() else self._file
        if what == QAbstractFileIconProvider.IconType.Drive:
            return self._drive
        if what == QAbstractFileIconProvider.IconType.Folder:
            return self._folder
        return self._file


_Option = QFileDialog.Option
_Mode = QFileDialog.FileMode


def _sidebar() -> list[QUrl]:
    locations = (
        QStandardPaths.StandardLocation.HomeLocation,
        QStandardPaths.StandardLocation.DesktopLocation,
        QStandardPaths.StandardLocation.DocumentsLocation,
        QStandardPaths.StandardLocation.DownloadLocation,
    )
    urls: list[QUrl] = []
    for location in locations:
        path = QStandardPaths.writableLocation(location)
        if path and Path(path).is_dir() and QUrl.fromLocalFile(path) not in urls:
            urls.append(QUrl.fromLocalFile(path))
    volumes = Path("/Volumes")
    urls.append(QUrl.fromLocalFile(str(volumes if volumes.is_dir() else Path("/"))))
    return urls


class ForgeFileDialog(FramedDialog):
    """Qt's file dialog embedded in a Forge frame."""

    def __init__(self, title: str, directory: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent, resizable=True)
        self.setObjectName("fileDialog")
        self.files = QFileDialog(self.body, title, directory)
        self.files.setOption(_Option.DontUseNativeDialog, True)
        # Without the Window flag the dialog becomes a plain embedded widget.
        self.files.setWindowFlags(Qt.WindowType.Widget)
        self.files.setSidebarUrls(_sidebar())
        self.files.finished.connect(self.done)
        if current_theme is not None:
            self._style(current_theme)
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(10, 8, 10, 4)
        layout.addWidget(self.files)
        self.resize(880, 540)

    def _style(self, theme: Theme) -> None:
        self._icons = _IconProvider(theme)
        self.files.setIconProvider(self._icons)
        for name, icon in _TOOL_ICONS.items():
            button = self.files.findChild(QToolButton, name)
            if button is not None:
                button.setIcon(themed_icon(icon, theme.text_muted, theme.text, theme.text_disabled))
                button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        for view in self.files.findChildren(QAbstractItemView):
            view.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        splitter = self.files.findChild(QSplitter, "splitter")
        if splitter is not None:
            splitter.setSizes([180, 680])
        tree = self.files.findChild(QTreeView, "treeView")
        header = tree.header() if tree is not None else None
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for column in (1, 2, 3):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)


def get_open_files(parent: QWidget, title: str, directory: str) -> list[str]:
    if use_native_dialogs:
        return QFileDialog.getOpenFileNames(parent, title, directory)[0]
    dialog = ForgeFileDialog(title, directory, parent)
    dialog.files.setFileMode(_Mode.ExistingFiles)
    if dialog.exec() != FramedDialog.DialogCode.Accepted:
        return []
    return dialog.files.selectedFiles()


def get_save_file(
    parent: QWidget, title: str, proposed: str, filters: list[str], selected: str
) -> tuple[str, str]:
    """The chosen path and the chosen filter, or ("", "") when cancelled."""
    if use_native_dialogs:
        return QFileDialog.getSaveFileName(parent, title, proposed, ";;".join(filters), selected)
    dialog = ForgeFileDialog(title, str(Path(proposed).parent), parent)
    files = dialog.files
    files.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    files.setFileMode(_Mode.AnyFile)
    files.setNameFilters(filters)
    files.selectNameFilter(selected)
    files.selectFile(Path(proposed).name)
    if dialog.exec() != FramedDialog.DialogCode.Accepted or not files.selectedFiles():
        return "", ""
    return files.selectedFiles()[0], files.selectedNameFilter()


def get_folder(parent: QWidget, title: str, directory: str) -> str:
    if use_native_dialogs:
        return QFileDialog.getExistingDirectory(parent, title, directory)
    dialog = ForgeFileDialog(title, directory, parent)
    dialog.files.setFileMode(_Mode.Directory)
    dialog.files.setOption(_Option.ShowDirsOnly, True)
    if dialog.exec() != FramedDialog.DialogCode.Accepted or not dialog.files.selectedFiles():
        return ""
    return dialog.files.selectedFiles()[0]

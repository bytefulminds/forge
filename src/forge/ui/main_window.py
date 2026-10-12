"""The Forge main window: menus, tabs and status bar."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Iterable
from functools import partial
from pathlib import Path

from PyQt6.QtCore import QByteArray, QEvent, QObject, QPoint, Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from forge import APP_NAME, __version__
from forge.core.document import Document
from forge.core.encoding import TextEncoding, can_encode, reinterpret
from forge.core.eol import Eol
from forge.core.fileio import LoadedBytes, LoadedText, load_text, load_utf8, save_text
from forge.core.session import SessionState, TabState, load_session, read_backup
from forge.core.session import save_session as write_session
from forge.core.settings import Settings
from forge.core.tasks import run_in_background
from forge.core.watcher import FileWatcher
from forge.editor import search
from forge.editor.commenting import CommentMode
from forge.editor.lexers import (
    PLAIN_TEXT,
    Language,
    all_languages,
    is_known_filename,
    language_by_id,
    language_for_path,
)
from forge.i18n.catalog import LANGUAGES
from forge.i18n.translator import current_language, tr
from forge.themes.theme import THEMES, Theme, get_theme
from forge.ui.appearance import apply_theme as apply_app_theme
from forge.ui.appearance import round_popup_menus
from forge.ui.document_tab import DocumentTab
from forge.ui.find_bar import FindBar
from forge.ui.format_menus import EncodingMenu, EolMenu
from forge.ui.goto_dialog import GoToLineDialog
from forge.ui.language_picker import LanguageMenu
from forge.ui.notice_bar import Notice, NoticeBar
from forge.ui.status_bar import ForgeStatusBar
from forge.ui.title_bar import EdgeResizer, WindowHeader

log = logging.getLogger(__name__)

IS_MAC = sys.platform == "darwin"
NEW_TAB_BUTTON_SIZE = 24
# Tabs have a 4 px top margin; this centers the close button on the visible tab.
TAB_BUTTON_TOP_OFFSET = 4
# Unsaved work is written to the session folder this often (and on quit).
SESSION_AUTOSAVE_MS = 7000
# Files from this size load on a background thread with progress.
ASYNC_LOAD_BYTES = 2_000_000
# Files from this size open without highlighting, word wrap and folding.
LARGE_FILE_BYTES = 20_000_000
Shortcut = QKeySequence.StandardKey | str | None

# Notepad++ shortcuts on Linux; macOS conventions where they differ.
# Qt turns "Ctrl" into Cmd and "Alt" into Option on macOS.
SAVE_AS_SHORTCUT = "Ctrl+Shift+S" if IS_MAC else "Ctrl+Alt+S"
SAVE_ALL_SHORTCUT = "Ctrl+Alt+S" if IS_MAC else "Ctrl+Shift+S"
# Notepad++: Ctrl+Q toggles a line comment. On macOS Cmd+Q must stay Quit, so the
# physical Control key is used there ("Meta" in Qt), plus the common Cmd+/.
TOGGLE_COMMENT_SHORTCUTS = ["Meta+Q", "Ctrl+/"] if IS_MAC else ["Ctrl+Q", "Ctrl+/"]
# Notepad++ quits with Alt+F4 on Linux; macOS keeps Cmd+Q.
# Search: Notepad++ keys on Linux. On macOS Cmd+H hides the app and Cmd+G is
# "find next" everywhere, so replace and go to line move (Cmd+Option+F, Cmd+L).
FIND_NEXT_SHORTCUTS = ["F3", "Ctrl+G"] if IS_MAC else ["F3"]
FIND_PREVIOUS_SHORTCUTS = ["Shift+F3", "Ctrl+Shift+G"] if IS_MAC else ["Shift+F3"]
REPLACE_SHORTCUT = "Ctrl+Alt+F" if IS_MAC else "Ctrl+H"
GO_TO_LINE_SHORTCUT = "Ctrl+L" if IS_MAC else "Ctrl+G"
EXIT_SHORTCUT: Shortcut = QKeySequence.StandardKey.Quit if IS_MAC else "Alt+F4"


def language_filter(language: Language) -> str:
    """File dialog filter for a language, e.g. ``JSON (*.json *.jsonc)``."""
    name = tr("Normal text") if language is PLAIN_TEXT else language.name
    patterns = " ".join(f"*{ext}" for ext in language.extensions)
    return f"{name} ({patterns})"


def all_files_filter() -> str:
    return tr("All files (*)")


def path_for_save(chosen: Path, language: Language, language_filter_selected: bool) -> Path:
    """Add the language's default extension when the user typed a name without one.

    Only when the language filter was selected in the dialog, never twice (the
    macOS save panel may already have added it), and never for dotfiles or
    names that identify a language on their own (Makefile).
    """
    if not language_filter_selected or not language.default_extension:
        return chosen
    if chosen.suffix or chosen.name.startswith(".") or is_known_filename(chosen):
        return chosen
    return chosen.with_name(chosen.name + language.default_extension)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, icon: QIcon | None = None) -> None:
        super().__init__()
        # Frameless everywhere: Forge draws its own title bar so it looks the
        # same on macOS, Linux and Windows.
        self._frameless = True
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.settings = settings
        self.theme: Theme = get_theme(settings.appearance.theme)
        self._last_dir = Path.home()

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tabs.currentChanged.connect(self._on_current_changed)
        self.notice_bar = NoticeBar(self)
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.tabs)
        # Find bar and notices sit below the editor, right above the status bar.
        self.find_bar = FindBar(self.current_tab, lambda text: self.status.showMessage(text, 4000))
        central_layout.addWidget(self.find_bar)
        central_layout.addWidget(self.notice_bar)
        self.setCentralWidget(central)
        self.watcher = FileWatcher(self)
        self.watcher.changed.connect(self._on_changed_on_disk)
        self.watcher.deleted.connect(self._on_deleted_on_disk)

        bar = self._tab_bar()
        bar.setUsesScrollButtons(True)
        bar.tabBarDoubleClicked.connect(self._on_tab_bar_double_clicked)
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._show_tab_menu)
        bar.installEventFilter(self)
        bar.tabMoved.connect(lambda *_: self._position_new_tab_button())
        self.tabs.installEventFilter(self)

        # "+" right after the last tab, like a browser. The empty corner widget
        # reserves room for it when the tabs fill the whole width.
        reserve = QWidget(self.tabs)
        reserve.setFixedSize(NEW_TAB_BUTTON_SIZE + 12, 1)
        self.tabs.setCornerWidget(reserve, Qt.Corner.TopRightCorner)
        self._new_tab_button = QToolButton(self.tabs)
        self._new_tab_button.setObjectName("newTabButton")
        self._new_tab_button.setText("+")
        self._new_tab_button.setFixedSize(NEW_TAB_BUTTON_SIZE, NEW_TAB_BUTTON_SIZE)
        self._new_tab_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_tab_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._new_tab_button.setToolTip(tr("New Tab"))
        self._new_tab_button.clicked.connect(self.new_document)

        self._menu_bar = QMenuBar(self)
        self._build_menus()
        round_popup_menus(self._menu_bar)
        self.header = WindowHeader(self, self._menu_bar, icon)
        self.title_bar = self.header.title_bar
        self.setMenuWidget(self.header)
        if self._frameless:
            self._resizer = EdgeResizer(self)
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self._resizer)
            self._update_frame_margins()
        self.status = ForgeStatusBar(
            self._language_menu, self._eol_status_menu, self._encoding_status_menu, self
        )
        self.status.position.clicked.connect(self.go_to_line)
        self.setStatusBar(self.status)

        self.setAcceptDrops(True)
        self._restore_geometry()
        self.apply_theme(self.theme)

        self._session_changed = False
        self._restoring = False
        self.restore_session()
        if self.tabs.count() == 0:
            self.new_document()
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(SESSION_AUTOSAVE_MS)
        self._session_timer.timeout.connect(self._autosave_session)
        self._session_timer.start()

    # Tabs ----------------------------------------------------------------

    def _tab_bar(self) -> QTabBar:
        bar = self.tabs.tabBar()
        assert bar is not None
        return bar

    def tab_at(self, index: int) -> DocumentTab | None:
        widget = self.tabs.widget(index)
        return widget if isinstance(widget, DocumentTab) else None

    def all_tabs(self) -> list[DocumentTab]:
        return [tab for i in range(self.tabs.count()) if (tab := self.tab_at(i)) is not None]

    def current_tab(self) -> DocumentTab | None:
        return self.tab_at(self.tabs.currentIndex())

    def _next_untitled_index(self) -> int:
        used = {tab.doc.untitled_index for tab in self.all_tabs() if tab.doc.is_untitled}
        index = 1
        while index in used:
            index += 1
        return index

    def _add_tab(self, document: Document, text: str = "") -> DocumentTab:
        tab = DocumentTab(document, self.settings.editor, self.theme)
        tab.set_language(language_for_path(document.path))
        tab.setText(text)
        tab.set_eol(document.eol)
        tab.setModified(False)
        tab.SendScintilla(DocumentTab.SCI_EMPTYUNDOBUFFER)
        tab.modificationChanged.connect(lambda _dirty, t=tab: self._refresh_tab(t))
        tab.cursorPositionChanged.connect(lambda *_args, t=tab: self._on_cursor_moved(t))
        tab.selectionChanged.connect(lambda t=tab: self._on_cursor_moved(t))
        tab.files_dropped.connect(self.open_paths)
        tab.textChanged.connect(self._mark_session_changed)
        index = self.tabs.addTab(tab, tab.title)
        self._add_close_button(index, tab)
        self.tabs.setCurrentIndex(index)
        self._refresh_tab(tab)
        tab.setFocus()
        QTimer.singleShot(0, self._position_new_tab_button)
        return tab

    def _add_close_button(self, index: int, tab: DocumentTab) -> None:
        bar = self._tab_bar()
        button = QToolButton(bar)
        button.setObjectName("tabCloseButton")
        button.setText("×")
        button.setAutoRaise(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tr("Close"))
        button.clicked.connect(lambda _checked=False, t=tab: self.close_tab(t))
        button.installEventFilter(self)
        # A small box with margins keeps the button inside the tab instead of
        # on its edge.
        box = QWidget(bar)
        box.setObjectName("tabButtonBox")
        layout = QHBoxLayout(box)
        layout.setContentsMargins(4, TAB_BUTTON_TOP_OFFSET, 8, 0)
        layout.setSpacing(0)
        layout.addWidget(button)
        tab.close_button = button
        bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, box)

    def _position_new_tab_button(self) -> None:
        bar = self._tab_bar()
        button = self._new_tab_button
        geometry = bar.geometry()
        if bar.count():
            last = bar.tabRect(bar.count() - 1)
            x = geometry.x() + last.right() + 6
            y = geometry.y() + last.center().y() - button.height() // 2 + 2
        else:
            x, y = geometry.x() + 6, geometry.y() + 4
        x = min(x, self.tabs.width() - button.width() - 6)
        button.move(x, y)
        button.raise_()

    def _close_button(self, tab: DocumentTab) -> QToolButton | None:
        return tab.close_button

    def _refresh_tab(self, tab: DocumentTab) -> None:
        index = self.tabs.indexOf(tab)
        if index < 0:
            return
        self.tabs.setTabText(index, tab.title)
        self.tabs.setTabToolTip(index, str(tab.doc.path or tab.title))
        button = self._close_button(tab)
        if button is not None:
            # A dot replaces the close cross while there are unsaved changes,
            # so the tab never changes width. Hovering shows the cross again.
            dirty = tab.is_dirty
            button.setProperty("dirty", "true" if dirty else "false")
            if not button.underMouse():
                button.setText("●" if dirty else "×")
            style = button.style()
            if style is not None:
                style.unpolish(button)
                style.polish(button)
        if tab is self.current_tab():
            self._update_window_title()

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        if event is None:
            return False
        if isinstance(obj, QToolButton) and obj.objectName() == "tabCloseButton":
            if event.type() == QEvent.Type.Enter:
                obj.setText("×")
            elif event.type() == QEvent.Type.Leave:
                obj.setText("●" if obj.property("dirty") == "true" else "×")
        elif (obj is self.tabs.tabBar() or obj is self.tabs) and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.LayoutRequest,
        ):
            QTimer.singleShot(0, self._position_new_tab_button)
        elif obj is self.tabs.tabBar() and event.type() == QEvent.Type.MouseButtonRelease:
            assert isinstance(event, QMouseEvent)
            if event.button() == Qt.MouseButton.MiddleButton:
                tab = self.tab_at(self._tab_bar().tabAt(event.position().toPoint()))
                if tab is not None:
                    self.close_tab(tab)
                    return True
        return super().eventFilter(obj, event)

    def _update_window_title(self) -> None:
        tab = self.current_tab()
        if tab is None:
            self.setWindowTitle(APP_NAME)
            return
        # Same title on every platform; Forge draws it in its own title bar.
        name = str(tab.doc.path) if tab.doc.path else tab.title
        self.setWindowTitle(f"{'*' if tab.is_dirty else ''}{name} - {APP_NAME}")

    def _on_current_changed(self, _index: int) -> None:
        self._mark_session_changed()
        tab = self.current_tab()
        self.status.show_tab(tab)
        self._update_window_title()
        self._sync_language_menu(tab)
        self._show_notice_for(tab)
        self.find_bar.attach(tab)
        if tab is not None:
            tab.setFocus()

    def _on_cursor_moved(self, tab: DocumentTab) -> None:
        if tab is self.current_tab():
            self.status.update_position(tab)

    def _on_tab_bar_double_clicked(self, index: int) -> None:
        if index < 0:  # empty area of the tab bar, as in Notepad++
            self.new_document()

    def _show_tab_menu(self, pos: QPoint) -> None:
        bar = self._tab_bar()
        tab = self.tab_at(bar.tabAt(pos))
        if tab is None:
            return
        menu = QMenu(self)
        round_popup_menus(menu)
        menu.addAction(tr("Close"), lambda: self.close_tab(tab))
        menu.addAction(tr("Close Others"), lambda: self.close_others(tab))
        menu.addAction(tr("Close All"), self.close_all)
        menu.addSeparator()
        path = tab.doc.path
        copy_path = menu.addAction(tr("Copy Full Path"), lambda: self._copy(str(path)))
        copy_name = menu.addAction(tr("Copy File Name"), lambda: self._copy(tab.title))
        reveal_text = tr("Show in Finder") if IS_MAC else tr("Open Containing Folder")
        reveal = menu.addAction(reveal_text, lambda: self._reveal(path))
        for action in (copy_path, reveal):
            if action is not None:
                action.setEnabled(path is not None)
        if copy_name is not None:
            copy_name.setEnabled(True)
        menu.exec(bar.mapToGlobal(pos))

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    @staticmethod
    def _reveal(path: Path | None) -> None:
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    # File commands -------------------------------------------------------

    def _dialog_dir(self, tab: DocumentTab | None = None) -> Path:
        """Folder of the current file, else the last folder used, else home."""
        tab = tab or self.current_tab()
        if tab is not None and tab.doc.path is not None and tab.doc.path.parent.is_dir():
            return tab.doc.path.parent
        return self._last_dir if self._last_dir.is_dir() else Path.home()

    def new_document(self) -> DocumentTab:
        return self._add_tab(Document(untitled_index=self._next_untitled_index()))

    def open_dialog(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, tr("Open"), str(self._dialog_dir()))
        self.open_paths([Path(f) for f in files])

    def open_paths(self, paths: Iterable[Path]) -> None:
        for path in paths:
            self.open_path(path)

    def open_path(self, path: Path) -> DocumentTab | None:
        path = path.expanduser().resolve()
        for tab in self.all_tabs():
            if tab.doc.path == path:
                self.tabs.setCurrentWidget(tab)
                return tab
        if path.is_dir():
            return None
        if not path.exists():
            QMessageBox.warning(self, APP_NAME, tr("File not found: {path}", path=str(path)))
            return None

        self._last_dir = path.parent
        replace = self._single_pristine_untitled()
        tab = self._add_tab(Document(path=path))
        if not self._fill_from_disk(tab):
            self._remove_tab(tab)
            if self.tabs.count() == 0:
                self.new_document()
            return None
        if replace is not None:
            self._remove_tab(replace)
        return tab

    # Loading files -------------------------------------------------------

    def _fill_from_disk(
        self, tab: DocumentTab, after: Callable[[DocumentTab], None] | None = None
    ) -> bool:
        """Load ``tab.doc.path`` into ``tab``.

        Small files load immediately. Files from ASYNC_LOAD_BYTES are read on a
        background thread and fed to the editor in chunks while the status bar
        shows progress. From LARGE_FILE_BYTES highlighting, wrap and folding
        are switched off. Returns False when the file cannot be read at all.
        """
        path = tab.doc.path
        assert path is not None
        try:
            size = path.stat().st_size
        except OSError as exc:
            self._show_open_error(path, exc)
            return False
        if size >= LARGE_FILE_BYTES and not tab.large_file:
            tab.set_large_file_mode(True)

        if size < ASYNC_LOAD_BYTES:
            try:
                loaded = load_text(path)
            except OSError as exc:
                self._show_open_error(path, exc)
                return False
            self._apply_loaded(tab, loaded)
            tab.setText(loaded.text)
            tab.SendScintilla(DocumentTab.SCI_EMPTYUNDOBUFFER)
            tab.setModified(False)
            self._loaded(tab, size, after)
            return True

        tab.loading = True
        tab.setReadOnly(True)
        name = tab.title
        self.status.showMessage(tr("Loading {name}...", name=name))

        def on_loaded(loaded: LoadedBytes) -> None:
            if tab not in self.all_tabs() or tab.load_cancelled:
                return
            self.status.showMessage(tr("Opening {name}...", name=name))
            self._apply_loaded(tab, loaded)
            tab.setReadOnly(False)
            tab.load_utf8(loaded.utf8)
            tab.loading = False
            self.status.clearMessage()
            self._loaded(tab, size, after)

        def on_failed(exc: Exception) -> None:
            self.status.clearMessage()
            if tab in self.all_tabs():
                self._remove_tab(tab)
                if self.tabs.count() == 0:
                    self.new_document()
            self._show_open_error(path, exc)

        run_in_background(lambda: load_utf8(path), on_loaded, on_failed)
        return True

    def _apply_loaded(self, tab: DocumentTab, loaded: LoadedText | LoadedBytes) -> None:
        tab.doc.encoding = loaded.encoding
        tab.doc.eol = loaded.eol
        tab.set_eol(loaded.eol)

    def _loaded(
        self, tab: DocumentTab, size: int, after: Callable[[DocumentTab], None] | None
    ) -> None:
        path = tab.doc.path
        if path is not None:
            self.watcher.watch(path)
        if tab.large_file:
            megabytes = max(1, round(size / 1_000_000))
            self._set_notice(
                tab,
                Notice(
                    "info",
                    tr(
                        "Large file ({size} MB): syntax highlighting, word wrap and "
                        "folding are off to keep Forge fast.",
                        size=megabytes,
                    ),
                    [(tr("Turn Highlighting On"), lambda: self._leave_large_mode(tab))],
                ),
            )
        if after is not None:
            after(tab)
        if tab is self.current_tab():
            self.status.show_tab(tab)
            self._sync_menus(tab)

    def _leave_large_mode(self, tab: DocumentTab) -> None:
        self._set_notice(tab, None)
        tab.set_large_file_mode(False)

    def _show_open_error(self, path: Path, exc: Exception) -> None:
        log.warning("Could not open %s: %s", path, exc)
        QMessageBox.warning(
            self,
            APP_NAME,
            tr("Could not open {path}:\n{error}", path=str(path), error=str(exc)),
        )

    def _single_pristine_untitled(self) -> DocumentTab | None:
        """Notepad++ behavior: opening a file replaces a lone, empty 'new 1' tab."""
        tabs = self.all_tabs()
        if len(tabs) != 1:
            return None
        tab = tabs[0]
        pristine = tab.doc.is_untitled and not tab.is_dirty and tab.length() == 0
        return tab if pristine else None

    def save(self, tab: DocumentTab | None = None) -> bool:
        tab = tab or self.current_tab()
        if tab is None:
            return False
        if tab.loading:
            self.status.showMessage(tr("{name} is still loading.", name=tab.title), 3000)
            return False
        if tab.doc.path is None:
            return self.save_as(tab)
        return self._write(tab, tab.doc.path)

    def save_as(self, tab: DocumentTab | None = None) -> bool:
        tab = tab or self.current_tab()
        if tab is None:
            return False
        language = tab.language
        if tab.doc.path is not None:
            proposed = tab.doc.path
        else:
            proposed = self._dialog_dir(tab) / f"{tab.title}{language.default_extension}"
        lang_filter = language_filter(language)
        file, selected = QFileDialog.getSaveFileName(
            self,
            tr("Save As"),
            str(proposed),
            ";;".join((lang_filter, all_files_filter())),
            lang_filter,
        )
        if not file:
            return False
        chosen = Path(file).resolve()
        path = path_for_save(chosen, language, selected == lang_filter)
        if path != chosen and path.exists() and not self._confirm_overwrite(path):
            return False
        if any(other is not tab and other.doc.path == path for other in self.all_tabs()):
            QMessageBox.warning(
                self,
                APP_NAME,
                tr("{name} is already open in another tab. Close it first.", name=path.name),
            )
            return False
        if not self._write(tab, path):
            return False

        old_suffix = tab.doc.path.suffix.lower() if tab.doc.path else None
        if tab.doc.path is not None:
            self._unwatch_if_unused(tab.doc.path, ignore=tab)
        tab.doc.path = path
        self.watcher.watch(path)
        self._last_dir = path.parent
        # Only follow the extension when it names a real language and changed.
        # Saving a JSON document as "data" (no extension) keeps it JSON.
        detected = language_for_path(path)
        if detected is not PLAIN_TEXT and path.suffix.lower() != old_suffix:
            tab.set_language(detected)
        self._refresh_tab(tab)
        self.status.show_tab(tab)
        self._sync_language_menu(tab)
        return True

    def _confirm_overwrite(self, path: Path) -> bool:
        answer = QMessageBox.question(
            self,
            APP_NAME,
            tr("{name} already exists. Do you want to replace it?", name=path.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def save_all(self) -> None:
        for tab in self.all_tabs():
            if tab.is_dirty:
                self.tabs.setCurrentWidget(tab)
                if not self.save(tab):
                    return

    def _write(self, tab: DocumentTab, path: Path) -> bool:
        try:
            save_text(path, tab.text(), tab.doc.encoding)
        except UnicodeEncodeError:
            QMessageBox.warning(
                self,
                APP_NAME,
                tr(
                    "This document contains characters that cannot be saved as {encoding}. "
                    "Convert it to UTF-8 and try again.",
                    encoding=tab.doc.encoding.label,
                ),
            )
            return False
        except OSError as exc:
            log.warning("Could not save %s: %s", path, exc)
            QMessageBox.warning(
                self,
                APP_NAME,
                tr("Could not save {path}:\n{error}", path=str(path), error=str(exc)),
            )
            return False
        tab.setModified(False)
        if path == tab.doc.path:
            self.watcher.remember(path)
        if tab.notice is not None and tab.notice.kind == "warning":
            self._set_notice(tab, None)
        return True

    # Closing -------------------------------------------------------------

    def _confirm_discard(self, tab: DocumentTab) -> bool:
        """Ask to save a dirty tab. Returns False when the user cancels."""
        if not tab.is_dirty:
            return True
        self.tabs.setCurrentWidget(tab)
        buttons = (
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        answer = QMessageBox.question(
            self,
            APP_NAME,
            tr("Do you want to save the changes to {name}?", name=tab.title),
            buttons,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save(tab)
        return answer == QMessageBox.StandardButton.Discard

    def close_tab(self, tab: DocumentTab | None = None) -> bool:
        tab = tab or self.current_tab()
        if tab is None or not self._confirm_discard(tab):
            return False
        self._remove_tab(tab)
        if self.tabs.count() == 0:
            self.new_document()
        return True

    def close_others(self, keep: DocumentTab) -> bool:
        others = [tab for tab in self.all_tabs() if tab is not keep]
        return all(self.close_tab(tab) for tab in others)

    def close_all(self) -> bool:
        for tab in self.all_tabs():
            if not self._confirm_discard(tab):
                return False
        for tab in self.all_tabs():
            self._remove_tab(tab)
        self.new_document()
        return True

    def _remove_tab(self, tab: DocumentTab) -> None:
        tab.cancel_loading()
        if tab.doc.path is not None:
            self._unwatch_if_unused(tab.doc.path, ignore=tab)
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.removeTab(index)
        tab.deleteLater()
        self._mark_session_changed()
        QTimer.singleShot(0, self._position_new_tab_button)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if event is None:
            return
        # Notepad++ behavior: no questions on quit, everything (including
        # unsaved text) is kept in the session and restored on the next start.
        # Only when the session cannot be written do we fall back to asking.
        if not self.save_session():
            for tab in self.all_tabs():
                if not self._confirm_discard(tab):
                    event.ignore()
                    return
        self._session_timer.stop()
        self.settings.window.geometry = bytes(self.saveGeometry().toBase64().data()).decode()
        self.settings.save()
        event.accept()

    def changeEvent(self, event: QEvent | None) -> None:
        if (
            event is not None
            and event.type() == QEvent.Type.ActivationChange
            and self.isActiveWindow()
        ):
            # Like Notepad++: look for outside changes when Forge gets focus
            # (file system events are not reliable on network drives).
            self.watcher.check_all()
        if event is not None and event.type() == QEvent.Type.WindowStateChange:
            self.title_bar.update_state()
            self._update_frame_margins()
        super().changeEvent(event)

    def _update_frame_margins(self) -> None:
        """Leave room for the 1px border of the frameless window, except when maximized."""
        if self._frameless:
            margin = 0 if self.isMaximized() or self.isFullScreen() else 1
            self.setContentsMargins(margin, margin, margin, margin)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        if self._frameless and self.contentsMargins().left() > 0:
            painter = QPainter(self)
            painter.setPen(self.palette().color(self.palette().ColorRole.Mid))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
            painter.end()

    def _restore_geometry(self) -> None:
        encoded = self.settings.window.geometry
        if not encoded or not self.restoreGeometry(QByteArray.fromBase64(encoded.encode())):
            self.resize(1100, 720)

    # Session ---------------------------------------------------------------

    def _mark_session_changed(self) -> None:
        if not getattr(self, "_restoring", False):
            self._session_changed = True

    def _autosave_session(self) -> None:
        if self._session_changed:
            self.save_session()

    def session_snapshot(self) -> tuple[SessionState, dict[str, str]]:
        state = SessionState(active=max(0, self.tabs.currentIndex()))
        backups: dict[str, str] = {}
        for tab in self.all_tabs():
            doc = tab.doc
            line, index = tab.getCursorPosition()
            text = tab.text()
            unsaved = not tab.loading and (tab.is_dirty or (doc.is_untitled and bool(text)))
            backup = f"tab-{len(state.tabs) + 1}.txt" if unsaved else None
            if backup is not None:
                backups[backup] = text
            state.tabs.append(
                TabState(
                    path=str(doc.path) if doc.path else None,
                    untitled_index=doc.untitled_index,
                    codec=doc.encoding.codec,
                    bom=doc.encoding.bom,
                    eol=doc.eol.name,
                    language=tab.language.id,
                    dirty=unsaved,
                    backup=backup,
                    cursor_line=line,
                    cursor_index=index,
                    first_visible_line=tab.firstVisibleLine(),
                )
            )
        return state, backups

    def save_session(self) -> bool:
        state, backups = self.session_snapshot()
        try:
            write_session(state, backups)
        except OSError:
            log.exception("Could not save the session")
            return False
        self._session_changed = False
        return True

    def restore_session(self) -> None:
        state = load_session()
        self._restoring = True
        try:
            restored: list[DocumentTab | None] = [self._restore_tab(t) for t in state.tabs]
        finally:
            self._restoring = False
        tabs = [tab for tab in restored if tab is not None]
        if not tabs:
            return
        active = restored[state.active] if 0 <= state.active < len(restored) else None
        self.tabs.setCurrentWidget(active or tabs[-1])

    def _restore_tab(self, state: TabState) -> DocumentTab | None:
        path = Path(state.path) if state.path else None
        language = language_by_id(state.language)

        def place_cursor(tab: DocumentTab) -> None:
            tab.setCursorPosition(state.cursor_line, state.cursor_index)
            tab.setFirstVisibleLine(state.first_visible_line)

        if state.backup:
            text = read_backup(state.backup)
            if text is None:
                return None
            eol = Eol[state.eol] if state.eol in Eol.__members__ else Eol.LF
            document = Document(
                path=path,
                encoding=TextEncoding(state.codec, state.bom),
                eol=eol,
                untitled_index=state.untitled_index,
            )
            tab = self._add_tab(document, text)
            tab.set_language(language)
            if state.dirty:
                tab.setModified(True)
            if path is not None:
                self.watcher.watch(path)
            place_cursor(tab)
            return tab
        if path is None or not path.is_file():
            return None
        tab = self._add_tab(Document(path=path))
        tab.set_language(language)
        if not self._fill_from_disk(tab, after=place_cursor):
            self._remove_tab(tab)
            return None
        return tab

    # Notices -------------------------------------------------------------

    def _set_notice(self, tab: DocumentTab, notice: Notice | None) -> None:
        tab.notice = notice
        if tab is self.current_tab():
            self._show_notice_for(tab)

    def _show_notice_for(self, tab: DocumentTab | None) -> None:
        notice = tab.notice if tab is not None else None
        target = tab
        self.notice_bar.show_notice(
            notice, lambda: self._set_notice(target, None) if target is not None else None
        )

    # Changes made outside Forge --------------------------------------------

    def _tabs_for(self, path: Path) -> list[DocumentTab]:
        return [tab for tab in self.all_tabs() if tab.doc.path == path]

    def _unwatch_if_unused(self, path: Path, ignore: DocumentTab) -> None:
        if not any(tab is not ignore for tab in self._tabs_for(path)):
            self.watcher.unwatch(path)

    def _on_changed_on_disk(self, path: Path) -> None:
        for tab in self._tabs_for(path):
            if tab.loading:
                continue
            if not tab.is_dirty:
                # Nothing to lose: reload quietly and keep the view where it was.
                self.reload(tab)
                self.status.showMessage(
                    tr("{name} was reloaded because it changed on disk.", name=tab.title), 4000
                )
                continue
            self._set_notice(
                tab,
                Notice(
                    "warning",
                    tr(
                        "{name} was changed by another program. You also have unsaved "
                        "changes here.",
                        name=tab.title,
                    ),
                    [
                        (tr("Reload from Disk"), partial(self.reload, tab)),
                        (tr("Keep My Version"), partial(self._set_notice, tab, None)),
                    ],
                ),
            )

    def _on_deleted_on_disk(self, path: Path) -> None:
        for tab in self._tabs_for(path):
            # The text only exists in Forge now.
            tab.setModified(True)
            self._set_notice(
                tab,
                Notice(
                    "warning",
                    tr(
                        "{name} was deleted or moved by another program. Your text is "
                        "kept; save to write it to disk again.",
                        name=tab.title,
                    ),
                    [
                        (tr("Save"), partial(self.save, tab)),
                        (tr("Close Tab"), partial(self._discard_tab, tab)),
                    ],
                ),
            )

    def _discard_tab(self, tab: DocumentTab) -> None:
        self._remove_tab(tab)
        if self.tabs.count() == 0:
            self.new_document()

    def reload(self, tab: DocumentTab) -> None:
        """Replace the tab's text with the file on disk, keeping the view."""
        if tab.doc.path is None:
            return
        line, index = tab.getCursorPosition()
        first = tab.firstVisibleLine()
        self._set_notice(tab, None)

        def restore_view(t: DocumentTab) -> None:
            t.setCursorPosition(min(line, max(0, t.lines() - 1)), index)
            t.setFirstVisibleLine(first)

        if not self._fill_from_disk(tab, after=restore_view):
            return

    # Encoding and line endings ----------------------------------------------

    def convert_eol(self, eol: Eol) -> None:
        tab = self.current_tab()
        if tab is None or tab.loading or eol is tab.doc.eol:
            return
        tab.convert_eols(eol)
        tab.doc.eol = eol
        self.status.show_tab(tab)
        self._sync_menus(tab)
        self._mark_session_changed()

    def convert_encoding(self, encoding: TextEncoding) -> None:
        """Keep the text, save it in ``encoding`` from now on."""
        tab = self.current_tab()
        if tab is None or tab.loading or encoding == tab.doc.encoding:
            return
        if not can_encode(tab.text(), encoding):
            QMessageBox.warning(
                self,
                APP_NAME,
                tr(
                    "This document contains characters that {encoding} cannot store.",
                    encoding=encoding.label,
                ),
            )
            self._sync_menus(tab)
            return
        tab.doc.encoding = encoding
        tab.setModified(True)
        self.status.show_tab(tab)
        self._sync_menus(tab)
        self._mark_session_changed()

    def reinterpret_encoding(self, encoding: TextEncoding) -> None:
        """Read the file on disk again as ``encoding`` (Notepad++ Encoding > X)."""
        tab = self.current_tab()
        if tab is None or tab.loading:
            return
        path = tab.doc.path
        if path is None:
            # Nothing on disk to reinterpret: just use it when saving.
            tab.doc.encoding = encoding
            self.status.show_tab(tab)
            self._sync_menus(tab)
            return
        if tab.is_dirty:
            answer = QMessageBox.question(
                self,
                APP_NAME,
                tr(
                    "Reloading {name} as {encoding} discards your unsaved changes. Continue?",
                    name=tab.title,
                    encoding=encoding.label,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._sync_menus(tab)
                return
        try:
            text = reinterpret(path.read_bytes(), encoding)
        except UnicodeDecodeError:
            QMessageBox.warning(
                self,
                APP_NAME,
                tr("{name} is not valid {encoding}.", name=tab.title, encoding=encoding.label),
            )
            self._sync_menus(tab)
            return
        except OSError as exc:
            self._show_open_error(path, exc)
            return
        line, index = tab.getCursorPosition()
        tab.doc.encoding = encoding
        tab.setText(text)
        tab.SendScintilla(DocumentTab.SCI_EMPTYUNDOBUFFER)
        tab.setModified(False)
        tab.setCursorPosition(min(line, max(0, tab.lines() - 1)), index)
        self.status.show_tab(tab)
        self._sync_menus(tab)

    # Search ----------------------------------------------------------------

    def open_find(self) -> None:
        self.find_bar.open_bar(replace=False)

    def open_replace(self) -> None:
        self.find_bar.open_bar(replace=True)

    def go_to_line(self) -> None:
        tab = self.current_tab()
        if tab is None:
            return
        line, _ = tab.getCursorPosition()
        dialog = GoToLineDialog(line + 1, tab.lines(), self)
        if dialog.exec() == GoToLineDialog.DialogCode.Accepted:
            search.go_to_line(tab, dialog.line)
        tab.setFocus()

    # Drag and drop on the window (tab bar, empty areas) -------------------

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:
        if event is not None and (mime := event.mimeData()) and mime.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event is not None and (mime := event.mimeData()) and mime.hasUrls():
            self.open_paths(Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile())
            event.acceptProposedAction()

    # Appearance and view settings -----------------------------------------

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_app_theme(app, theme)
        for tab in self.all_tabs():
            tab.apply_theme(theme)

    def set_theme(self, theme_id: str) -> None:
        self.settings.appearance.theme = theme_id
        self.apply_theme(get_theme(theme_id))
        self.settings.save()

    def _apply_editor_settings(self) -> None:
        for tab in self.all_tabs():
            tab.apply_settings(self.settings.editor)
        self.settings.save()

    def _toggle_word_wrap(self, checked: bool) -> None:
        self.settings.editor.word_wrap = checked
        self._apply_editor_settings()

    def _toggle_whitespace(self, checked: bool) -> None:
        self.settings.editor.show_whitespace = checked
        self._apply_editor_settings()

    def _toggle_line_numbers(self, checked: bool) -> None:
        self.settings.editor.show_line_numbers = checked
        self._apply_editor_settings()

    def _zoom(self, steps: int) -> None:
        tab = self.current_tab()
        if tab is None:
            return
        if steps == 0:
            tab.zoomTo(0)
        elif steps > 0:
            tab.zoomIn()
        else:
            tab.zoomOut()

    def set_interface_language(self, language: str) -> None:
        if language == self.settings.appearance.language:
            return
        self.settings.appearance.language = language
        self.settings.save()
        if language != current_language():
            QMessageBox.information(self, APP_NAME, tr("Restart Forge to use the new language."))

    def set_document_language(self, language: Language) -> None:
        tab = self.current_tab()
        if tab is not None:
            tab.set_language(language)
            self.status.show_tab(tab)
            self._sync_language_menu(tab)

    # Edit commands ---------------------------------------------------------

    def _comment(self, mode: CommentMode) -> None:
        tab = self.current_tab()
        if tab is not None and not tab.comment_lines(mode):
            name = tr("Normal text") if tab.language is PLAIN_TEXT else tab.language.name
            self.status.showMessage(tr("{language} has no comment syntax", language=name), 3000)

    def _on_editor(self, method: str) -> Callable[[], None]:
        def run() -> None:
            tab = self.current_tab()
            if tab is not None:
                getattr(tab, method)()

        return run

    # Menus ---------------------------------------------------------------

    def _action(
        self,
        menu: QMenu,
        text: str,
        slot: Callable[..., object],
        shortcut: Shortcut = None,
        role: QAction.MenuRole = QAction.MenuRole.NoRole,
    ) -> QAction:
        action = QAction(text, self)
        if isinstance(shortcut, QKeySequence.StandardKey):
            action.setShortcuts(shortcut)
        elif isinstance(shortcut, str):
            action.setShortcut(QKeySequence(shortcut))
        # NoRole by default, so Qt never moves items into the macOS app menu
        # based on their text.
        action.setMenuRole(role)
        action.triggered.connect(lambda _checked=False: slot())
        menu.addAction(action)
        return action

    def _checkable(
        self, menu: QMenu, text: str, checked: bool, slot: Callable[[bool], None]
    ) -> QAction:
        action = QAction(text, self)
        action.setCheckable(True)
        action.setChecked(checked)
        action.setMenuRole(QAction.MenuRole.NoRole)
        action.toggled.connect(slot)
        menu.addAction(action)
        return action

    def _build_menus(self) -> None:
        bar = self._menu_bar
        sk = QKeySequence.StandardKey

        file_menu = bar.addMenu(tr("&File"))
        assert file_menu is not None
        self._action(file_menu, tr("&New"), self.new_document, sk.New)
        self._action(file_menu, tr("&Open..."), self.open_dialog, sk.Open)
        file_menu.addSeparator()
        self._action(file_menu, tr("&Save"), self.save, sk.Save)
        self._action(file_menu, tr("Save &As..."), self.save_as, SAVE_AS_SHORTCUT)
        self._action(file_menu, tr("Sa&ve All"), self.save_all, SAVE_ALL_SHORTCUT)
        file_menu.addSeparator()
        self._action(file_menu, tr("&Close"), self.close_tab, sk.Close)
        self._action(file_menu, tr("Clos&e All"), self.close_all, "Ctrl+Shift+W")
        file_menu.addSeparator()
        self._action(file_menu, tr("E&xit"), self.close, EXIT_SHORTCUT, QAction.MenuRole.QuitRole)

        edit_menu = bar.addMenu(tr("&Edit"))
        assert edit_menu is not None
        self._action(edit_menu, tr("&Undo"), self._on_editor("undo"), sk.Undo)
        self._action(edit_menu, tr("&Redo"), self._on_editor("redo"), sk.Redo)
        edit_menu.addSeparator()
        self._action(edit_menu, tr("Cu&t"), self._on_editor("cut"), sk.Cut)
        self._action(edit_menu, tr("&Copy"), self._on_editor("copy"), sk.Copy)
        self._action(edit_menu, tr("&Paste"), self._on_editor("paste"), sk.Paste)
        self._action(edit_menu, tr("&Delete"), self._on_editor("removeSelectedText"))
        edit_menu.addSeparator()
        self._action(edit_menu, tr("Select &All"), self._on_editor("selectAll"), sk.SelectAll)
        edit_menu.addSeparator()
        self._eol_menu = EolMenu(tr("&EOL Conversion"), self)
        self._eol_menu.eol_chosen.connect(self.convert_eol)
        edit_menu.addMenu(self._eol_menu)
        comment_menu = edit_menu.addMenu(tr("C&omment/Uncomment"))
        assert comment_menu is not None
        toggle = self._action(
            comment_menu,
            tr("&Toggle Single Line Comment"),
            lambda: self._comment(CommentMode.TOGGLE),
        )
        toggle.setShortcuts([QKeySequence(k) for k in TOGGLE_COMMENT_SHORTCUTS])
        self._action(
            comment_menu,
            tr("Single Line &Comment"),
            lambda: self._comment(CommentMode.COMMENT),
            "Ctrl+K",
        )
        self._action(
            comment_menu,
            tr("Single Line &Uncomment"),
            lambda: self._comment(CommentMode.UNCOMMENT),
            "Ctrl+Shift+K",
        )

        search_menu = bar.addMenu(tr("&Search"))
        assert search_menu is not None
        self._action(search_menu, tr("&Find..."), self.open_find, sk.Find)
        find_next = self._action(search_menu, tr("Find &Next"), self.find_bar.find_next)
        find_next.setShortcuts([QKeySequence(k) for k in FIND_NEXT_SHORTCUTS])
        find_previous = self._action(search_menu, tr("Find &Previous"), self.find_bar.find_previous)
        find_previous.setShortcuts([QKeySequence(k) for k in FIND_PREVIOUS_SHORTCUTS])
        self._action(search_menu, tr("&Replace..."), self.open_replace, REPLACE_SHORTCUT)
        search_menu.addSeparator()
        self._action(search_menu, tr("&Go To..."), self.go_to_line, GO_TO_LINE_SHORTCUT)

        view_menu = bar.addMenu(tr("&View"))
        assert view_menu is not None
        ed = self.settings.editor
        wrap_text = tr("Word &Wrap")
        whitespace_text = tr("Show White&space and Line Endings")
        numbers_text = tr("Show &Line Numbers")
        self._checkable(view_menu, wrap_text, ed.word_wrap, self._toggle_word_wrap)
        self._checkable(view_menu, whitespace_text, ed.show_whitespace, self._toggle_whitespace)
        self._checkable(view_menu, numbers_text, ed.show_line_numbers, self._toggle_line_numbers)
        view_menu.addSeparator()
        self._action(view_menu, tr("Zoom &In"), lambda: self._zoom(1), sk.ZoomIn)
        self._action(view_menu, tr("Zoom &Out"), lambda: self._zoom(-1), sk.ZoomOut)
        self._action(view_menu, tr("&Reset Zoom"), lambda: self._zoom(0), "Ctrl+0")

        self._encoding_menu = EncodingMenu(tr("E&ncoding"), self)
        self._encoding_menu.reinterpret_chosen.connect(self.reinterpret_encoding)
        self._encoding_menu.convert_chosen.connect(self.convert_encoding)
        bar.addMenu(self._encoding_menu)
        # Separate instances for the status bar segments (a QMenu can only
        # belong to one parent menu).
        self._eol_status_menu = EolMenu(tr("&EOL Conversion"), self)
        self._eol_status_menu.eol_chosen.connect(self.convert_eol)
        self._encoding_status_menu = EncodingMenu(tr("E&ncoding"), self)
        self._encoding_status_menu.reinterpret_chosen.connect(self.reinterpret_encoding)
        self._encoding_status_menu.convert_chosen.connect(self.convert_encoding)
        round_popup_menus(self._eol_status_menu)
        round_popup_menus(self._encoding_status_menu)

        self._language_menu = LanguageMenu(tr("&Language"), all_languages(), self)
        self._language_menu.language_chosen.connect(self.set_document_language)
        bar.addMenu(self._language_menu)

        settings_menu = bar.addMenu(tr("Se&ttings"))
        assert settings_menu is not None
        theme_menu = settings_menu.addMenu(tr("&Theme"))
        assert theme_menu is not None
        theme_group = QActionGroup(self)
        theme_labels = {"dark": tr("Forge Dark"), "light": tr("Forge Light")}
        for theme_id in THEMES:
            action = QAction(theme_labels.get(theme_id, theme_id), theme_group)
            action.setCheckable(True)
            action.setChecked(theme_id == self.theme.id)
            action.setMenuRole(QAction.MenuRole.NoRole)
            action.triggered.connect(lambda _c=False, tid=theme_id: self.set_theme(tid))
            theme_menu.addAction(action)

        ui_language_menu = settings_menu.addMenu(tr("&Interface Language"))
        assert ui_language_menu is not None
        ui_group = QActionGroup(self)
        configured = self.settings.appearance.language
        system_action = QAction(tr("System Default"), ui_group)
        system_action.setCheckable(True)
        system_action.setChecked(configured not in LANGUAGES)
        system_action.setMenuRole(QAction.MenuRole.NoRole)
        system_action.triggered.connect(lambda _c=False: self.set_interface_language(""))
        ui_language_menu.addAction(system_action)
        ui_language_menu.addSeparator()
        for code, name in LANGUAGES.items():
            action = QAction(name, ui_group)
            action.setCheckable(True)
            action.setChecked(code == configured)
            action.setMenuRole(QAction.MenuRole.NoRole)
            action.triggered.connect(lambda _c=False, lc=code: self.set_interface_language(lc))
            ui_language_menu.addAction(action)

        help_menu = bar.addMenu(tr("&Help"))
        assert help_menu is not None
        about_role = QAction.MenuRole.AboutRole
        self._action(help_menu, tr("&About Forge"), self.show_about, role=about_role)

    def _sync_language_menu(self, tab: DocumentTab | None) -> None:
        self._sync_menus(tab)

    def _sync_menus(self, tab: DocumentTab | None) -> None:
        if tab is None:
            return
        self._language_menu.set_current(tab.language)
        for eol_menu in (self._eol_menu, self._eol_status_menu):
            eol_menu.set_current(tab.doc.eol)
        for encoding_menu in (self._encoding_menu, self._encoding_status_menu):
            encoding_menu.set_current(tab.doc.encoding)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("About Forge"),
            tr(
                "<h3>Forge {version}</h3>"
                "<p>Your tools. Your workflow.</p>"
                "<p>A fast, lightweight text editor for macOS and Linux.</p>"
                "<p>Licensed under the GNU GPL v3.</p>",
                version=__version__,
            ),
        )

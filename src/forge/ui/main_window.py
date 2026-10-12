"""The Forge main window: menus, tabs and status bar."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTabBar,
    QTabWidget,
    QToolButton,
)

from forge import APP_NAME, __version__
from forge.core.document import Document
from forge.core.fileio import load_text, save_text
from forge.core.settings import Settings
from forge.editor.lexers import Language, all_languages, language_for_path
from forge.i18n.catalog import LANGUAGES
from forge.i18n.translator import current_language, tr
from forge.themes.qss import build_stylesheet
from forge.themes.theme import THEMES, Theme, get_theme
from forge.ui.document_tab import DocumentTab
from forge.ui.status_bar import ForgeStatusBar

log = logging.getLogger(__name__)

Shortcut = QKeySequence.StandardKey | str | None


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.theme: Theme = get_theme(settings.appearance.theme)

        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.currentChanged.connect(self._on_current_changed)
        self.setCentralWidget(self.tabs)

        self.status = ForgeStatusBar(self)
        self.setStatusBar(self.status)

        self._build_menus()
        self.setAcceptDrops(True)
        self.resize(1100, 720)
        self.apply_theme(self.theme)
        self.new_document()

    # Tabs ----------------------------------------------------------------

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
        index = self.tabs.addTab(tab, document.display_name)
        self._add_close_button(index, tab)
        self.tabs.setCurrentIndex(index)
        self._refresh_tab(tab)
        tab.setFocus()
        return tab

    def _add_close_button(self, index: int, tab: DocumentTab) -> None:
        bar = self.tabs.tabBar()
        if bar is None:
            return
        button = QToolButton(bar)
        button.setObjectName("tabCloseButton")
        button.setText("×")
        button.setAutoRaise(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tr("Close"))
        button.clicked.connect(lambda _checked=False, t=tab: self.close_tab(t))
        bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, button)

    def _refresh_tab(self, tab: DocumentTab) -> None:
        index = self.tabs.indexOf(tab)
        if index < 0:
            return
        marker = " ●" if tab.is_dirty else ""
        self.tabs.setTabText(index, f"{tab.doc.display_name}{marker}")
        self.tabs.setTabToolTip(index, str(tab.doc.path or tab.doc.display_name))
        if tab is self.current_tab():
            self._update_window_title()

    def _update_window_title(self) -> None:
        tab = self.current_tab()
        if tab is None:
            self.setWindowTitle(APP_NAME)
            return
        name = str(tab.doc.path) if tab.doc.path else tab.doc.display_name
        self.setWindowTitle(f"{'*' if tab.is_dirty else ''}{name} - {APP_NAME}")
        self.setWindowModified(tab.is_dirty)
        self.setWindowFilePath(str(tab.doc.path) if tab.doc.path else "")

    def _on_current_changed(self, _index: int) -> None:
        tab = self.current_tab()
        self.status.show_tab(tab)
        self._update_window_title()
        self._sync_language_menu(tab)

    def _on_cursor_moved(self, tab: DocumentTab) -> None:
        if tab is self.current_tab():
            self.status.update_position(tab)

    # File commands -------------------------------------------------------

    def new_document(self) -> DocumentTab:
        return self._add_tab(Document(untitled_index=self._next_untitled_index()))

    def open_dialog(self) -> None:
        start = ""
        tab = self.current_tab()
        if tab is not None and tab.doc.path is not None:
            start = str(tab.doc.path.parent)
        files, _ = QFileDialog.getOpenFileNames(self, tr("Open"), start)
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
        try:
            loaded = load_text(path) if path.exists() else None
        except OSError as exc:
            log.warning("Could not open %s: %s", path, exc)
            QMessageBox.warning(
                self,
                APP_NAME,
                tr("Could not open {path}:\n{error}", path=str(path), error=str(exc)),
            )
            return None
        if loaded is None:
            QMessageBox.warning(self, APP_NAME, tr("File not found: {path}", path=str(path)))
            return None

        document = Document(path=path, encoding=loaded.encoding, eol=loaded.eol)
        replace = self._single_pristine_untitled()
        tab = self._add_tab(document, loaded.text)
        if replace is not None:
            self._remove_tab(replace)
        return tab

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
        if tab.doc.path is None:
            return self.save_as(tab)
        return self._write(tab, tab.doc.path)

    def save_as(self, tab: DocumentTab | None = None) -> bool:
        tab = tab or self.current_tab()
        if tab is None:
            return False
        start = str(tab.doc.path) if tab.doc.path else tab.doc.display_name
        file, _ = QFileDialog.getSaveFileName(self, tr("Save As"), start)
        if not file:
            return False
        path = Path(file).resolve()
        if not self._write(tab, path):
            return False
        tab.doc.path = path
        tab.set_language(language_for_path(path))
        self._refresh_tab(tab)
        self.status.show_tab(tab)
        self._sync_language_menu(tab)
        return True

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
            tr("Save changes to {name}?", name=tab.doc.display_name),
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

    def close_all(self) -> bool:
        for tab in self.all_tabs():
            if not self._confirm_discard(tab):
                return False
        for tab in self.all_tabs():
            self._remove_tab(tab)
        self.new_document()
        return True

    def _remove_tab(self, tab: DocumentTab) -> None:
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.removeTab(index)
        tab.deleteLater()

    def _on_tab_close_requested(self, index: int) -> None:
        tab = self.tab_at(index)
        if tab is not None:
            self.close_tab(tab)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        if event is None:
            return
        for tab in self.all_tabs():
            if not self._confirm_discard(tab):
                event.ignore()
                return
        self.settings.save()
        event.accept()

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
            app.setStyleSheet(build_stylesheet(theme))
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

    def set_interface_language(self, language: str) -> None:
        if language == self.settings.appearance.language:
            return
        self.settings.appearance.language = language
        self.settings.save()
        if language != current_language():
            QMessageBox.information(
                self, APP_NAME, tr("The new language will be used after restarting Forge.")
            )

    def set_document_language(self, language: Language) -> None:
        tab = self.current_tab()
        if tab is not None:
            tab.set_language(language)
            self.status.show_tab(tab)

    # Edit commands ---------------------------------------------------------

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
        role: QAction.MenuRole | None = None,
    ) -> QAction:
        action = QAction(text, self)
        if isinstance(shortcut, QKeySequence.StandardKey):
            action.setShortcuts(shortcut)
        elif isinstance(shortcut, str):
            # "Ctrl" automatically becomes Cmd on macOS.
            action.setShortcut(QKeySequence(shortcut))
        if role is not None:
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
        action.toggled.connect(slot)
        menu.addAction(action)
        return action

    def _build_menus(self) -> None:
        bar = self.menuBar()
        assert bar is not None
        sk = QKeySequence.StandardKey

        file_menu = bar.addMenu(tr("&File"))
        assert file_menu is not None
        self._action(file_menu, tr("&New"), self.new_document, sk.New)
        self._action(file_menu, tr("&Open..."), self.open_dialog, sk.Open)
        file_menu.addSeparator()
        self._action(file_menu, tr("&Save"), self.save, sk.Save)
        self._action(file_menu, tr("Save &As..."), self.save_as, "Ctrl+Alt+S")
        self._action(file_menu, tr("Sa&ve All"), self.save_all, "Ctrl+Shift+S")
        file_menu.addSeparator()
        self._action(file_menu, tr("&Close"), self.close_tab, sk.Close)
        self._action(file_menu, tr("Clos&e All"), self.close_all, "Ctrl+Shift+W")
        file_menu.addSeparator()
        self._action(file_menu, tr("E&xit"), self.close, sk.Quit, QAction.MenuRole.QuitRole)

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

        view_menu = bar.addMenu(tr("&View"))
        assert view_menu is not None
        ed = self.settings.editor
        self._checkable(view_menu, tr("&Word Wrap"), ed.word_wrap, self._toggle_word_wrap)
        self._checkable(
            view_menu,
            tr("Show &Whitespace and Line Endings"),
            ed.show_whitespace,
            self._toggle_whitespace,
        )
        self._checkable(
            view_menu, tr("Show &Line Numbers"), ed.show_line_numbers, self._toggle_line_numbers
        )

        self._language_menu = bar.addMenu(tr("&Language"))
        assert self._language_menu is not None
        self._language_group = QActionGroup(self)
        self._language_actions: dict[str, QAction] = {}
        for language in all_languages():
            label = tr("Normal text") if language.lexer is None else language.name
            action = QAction(label, self._language_group)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _c=False, lang=language: self.set_document_language(lang)
            )
            self._language_menu.addAction(action)
            self._language_actions[language.id] = action

        settings_menu = bar.addMenu(tr("&Settings"))
        assert settings_menu is not None
        theme_menu = settings_menu.addMenu(tr("&Theme"))
        assert theme_menu is not None
        theme_group = QActionGroup(self)
        theme_labels = {"dark": tr("Forge Dark"), "light": tr("Forge Light")}
        for theme_id in THEMES:
            action = QAction(theme_labels.get(theme_id, theme_id), theme_group)
            action.setCheckable(True)
            action.setChecked(theme_id == self.theme.id)
            action.triggered.connect(lambda _c=False, tid=theme_id: self.set_theme(tid))
            theme_menu.addAction(action)

        ui_language_menu = settings_menu.addMenu(tr("&Interface Language"))
        assert ui_language_menu is not None
        ui_group = QActionGroup(self)
        configured = self.settings.appearance.language
        system_action = QAction(tr("System Default"), ui_group)
        system_action.setCheckable(True)
        system_action.setChecked(configured not in LANGUAGES)
        system_action.triggered.connect(lambda _c=False: self.set_interface_language(""))
        ui_language_menu.addAction(system_action)
        ui_language_menu.addSeparator()
        for code, name in LANGUAGES.items():
            action = QAction(name, ui_group)
            action.setCheckable(True)
            action.setChecked(code == configured)
            action.triggered.connect(lambda _c=False, lc=code: self.set_interface_language(lc))
            ui_language_menu.addAction(action)

        help_menu = bar.addMenu(tr("&Help"))
        assert help_menu is not None
        self._action(
            help_menu, tr("&About Forge"), self.show_about, role=QAction.MenuRole.AboutRole
        )

    def _sync_language_menu(self, tab: DocumentTab | None) -> None:
        if tab is None:
            return
        action = self._language_actions.get(tab.language.id)
        if action is not None:
            action.setChecked(True)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("About Forge"),
            tr(
                "<h3>Forge {version}</h3>"
                "<p>A fast, lightweight text editor for macOS and Linux.</p>"
                "<p>Licensed under the GNU GPL v3.</p>",
                version=__version__,
            ),
        )

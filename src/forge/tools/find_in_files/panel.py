"""Find in Files panel: search form above a results tree (opens below the editor)."""

from __future__ import annotations

import re
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI, tr
from forge.tools.find_in_files.engine import (
    FileResult,
    Query,
    Summary,
    parse_filters,
    replace_in_file,
    search,
)

_PATH_ROLE = 256
_HIT_ROLE = 257


class _Bridge(QObject):
    """Carries worker thread results to the UI thread (queued signals)."""

    result = pyqtSignal(object)
    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)


def _option(text: str, tooltip: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName("findOption")
    button.setText(text)
    button.setToolTip(tooltip)
    button.setCheckable(True)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button


class FindInFilesPanel(QWidget):
    def __init__(self, api: ForgeAPI) -> None:
        super().__init__()
        self.setObjectName("toolPanel")
        self._api = api
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._bridge = _Bridge(self)
        self._bridge.result.connect(self._add_result)
        self._bridge.progress.connect(self._progress)
        self._bridge.finished.connect(self._finished)
        self._bridge.failed.connect(self._failed)
        self._folder: Path | None = None
        self._results: list[FileResult] = []

        self.find_edit = QLineEdit(self)
        self.find_edit.setPlaceholderText(tr("Find"))
        self.find_edit.returnPressed.connect(self.find_all)
        self.replace_edit = QLineEdit(self)
        self.replace_edit.setPlaceholderText(tr("Replace with"))
        self.folder_edit = QLineEdit(self)
        self.folder_edit.setPlaceholderText(tr("Folder"))
        browse = QPushButton(tr("Browse..."), self)
        browse.clicked.connect(self._browse)
        self.filters_edit = QLineEdit(self)
        self.filters_edit.setPlaceholderText(tr("Filters, for example *.py *.json !build"))
        self.filters_edit.setToolTip(
            tr("File name patterns to search. Prefix with ! to skip files or folders.")
        )
        self.match_case = _option("Aa", tr("Match case"))
        self.whole_word = _option("W", tr("Match whole word only"))
        self.regex = _option(".*", tr("Regular expression"))
        self.recursive = QCheckBox(tr("Include subfolders"), self)
        self.recursive.setChecked(True)
        self.find_button = QPushButton(tr("Find All"), self)
        self.find_button.setProperty("primary", "true")
        self.find_button.clicked.connect(self.find_all)
        self.replace_button = QPushButton(tr("Replace in Files"), self)
        self.replace_button.clicked.connect(self.replace_all)
        self.cancel_button = QPushButton(tr("Cancel"), self)
        self.cancel_button.clicked.connect(self._cancel.set)
        self.cancel_button.setEnabled(False)
        self.status = QLabel(self)
        self.status.setObjectName("findCount")
        self.results = QTreeWidget(self)
        self.results.setHeaderHidden(True)
        self.results.setUniformRowHeights(True)
        self.results.itemActivated.connect(self._open_hit)
        self.results.itemDoubleClicked.connect(self._open_hit)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(self.find_edit, 0, 0)
        grid.addWidget(self.replace_edit, 0, 1)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)
        grid.addLayout(folder_row, 1, 0)
        grid.addWidget(self.filters_edit, 1, 1)
        options = QHBoxLayout()
        options.setSpacing(4)
        for widget in (self.match_case, self.whole_word, self.regex):
            options.addWidget(widget)
        options.addSpacing(8)
        options.addWidget(self.recursive)
        options.addSpacing(12)
        options.addWidget(self.status, 1)
        options.addWidget(self.find_button)
        options.addWidget(self.replace_button)
        options.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        layout.addLayout(grid)
        layout.addLayout(options)
        layout.addWidget(self.results, 1)

        self.folder_edit.setText(str(api.setting("folder", "") or api.dialog_dir()))
        self.filters_edit.setText(str(api.setting("filters", "") or ""))

    # Form ------------------------------------------------------------------

    def prepare(self) -> None:
        editor = self._api.active_editor()
        if editor is not None and editor.has_selection():
            selected = editor.selected_text()
            if "\n" not in selected:
                self.find_edit.setText(selected)
        if editor is not None and editor.path is not None and not self.folder_edit.text():
            self.folder_edit.setText(str(editor.path.parent))
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def _browse(self) -> None:
        folder = self._api.choose_folder(
            tr("Choose a Folder"), self.folder_edit.text() or str(self._api.dialog_dir())
        )
        if folder:
            self.folder_edit.setText(folder)

    def _query(self) -> Query | None:
        pattern = self.find_edit.text()
        folder = Path(self.folder_edit.text().strip()).expanduser()
        if not pattern:
            return None
        if not folder.is_dir():
            self.status.setText(tr("Folder not found."))
            return None
        include, exclude = parse_filters(self.filters_edit.text())
        query = Query(
            pattern=pattern,
            folder=folder,
            match_case=self.match_case.isChecked(),
            whole_word=self.whole_word.isChecked(),
            regex=self.regex.isChecked(),
            include=include,
            exclude=exclude,
            recursive=self.recursive.isChecked(),
        )
        try:
            query.compile()
        except re.error as exc:
            self.status.setText(tr("Invalid expression: {error}", error=str(exc)))
            return None
        self._api.set_setting("folder", str(folder))
        self._api.set_setting("filters", self.filters_edit.text())
        return query

    # Searching -------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def find_all(self) -> None:
        if self.busy:
            return
        query = self._query()
        if query is None:
            return
        self._folder = query.folder
        self._results = []
        self.results.clear()
        self.status.setText(tr("Searching..."))
        self._set_busy(True)
        self._cancel.clear()
        bridge = self._bridge
        cancel = self._cancel

        def work() -> None:
            try:
                summary = search(query, cancel, bridge.result.emit, bridge.progress.emit)
            except Exception as exc:
                bridge.failed.emit(str(exc))
                return
            bridge.finished.emit(summary)

        self._thread = threading.Thread(target=work, name="forge-find-in-files", daemon=True)
        self._thread.start()

    def wait(self, timeout: float = 10.0) -> None:
        """Block until a running search ends (used by tests)."""
        if self._thread is not None:
            self._thread.join(timeout)

    def _set_busy(self, busy: bool) -> None:
        self.find_button.setEnabled(not busy)
        self.replace_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    def _add_result(self, result: FileResult) -> None:
        self._results.append(result)
        folder = self._folder
        try:
            shown = result.path.relative_to(folder) if folder else result.path
        except ValueError:
            shown = result.path
        file_item = QTreeWidgetItem([f"{shown}  ({len(result.hits)})"])
        file_item.setData(0, _PATH_ROLE, str(result.path))
        for hit in result.hits[:1000]:
            text = hit.text.strip()
            if len(text) > 300:
                text = text[:300] + "…"
            child = QTreeWidgetItem([f"{hit.line}: {text}"])
            child.setData(0, _PATH_ROLE, str(result.path))
            child.setData(0, _HIT_ROLE, (hit.line, hit.column, hit.length))
            file_item.addChild(child)
        self.results.addTopLevelItem(file_item)
        if self.results.topLevelItemCount() <= 20:
            file_item.setExpanded(True)

    def _progress(self, files: int) -> None:
        self.status.setText(tr("Searching... {count} files", count=files))

    def _finished(self, summary: Summary) -> None:
        self._set_busy(False)
        text = tr(
            "{hits} matches in {files} files ({searched} searched)",
            hits=summary.hits,
            files=summary.files_matched,
            searched=summary.files_searched,
        )
        if summary.truncated:
            text += " " + tr("(stopped at the limit)")
        if summary.cancelled:
            text += " " + tr("(cancelled)")
        self.status.setText(text)

    def _failed(self, message: str) -> None:
        self._set_busy(False)
        self.status.setText(tr("Search failed: {error}", error=message))

    def _open_hit(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, _PATH_ROLE)
        if not path:
            return
        editor = self._api.open_file(Path(path))
        hit = item.data(0, _HIT_ROLE)
        if editor is not None and hit:
            line, column, length = hit
            editor.select(int(line), int(column), int(length))

    # Replacing -------------------------------------------------------------

    def replace_all(self) -> None:
        if self.busy:
            return
        query = self._query()
        if query is None:
            return
        confirmed = self._api.confirm(
            tr("Replace in Files"),
            tr(
                "Replace every match of '{find}' with '{replace}' in {folder}? "
                "Files are changed on disk; this cannot be undone with Undo.",
                find=query.pattern,
                replace=self.replace_edit.text(),
                folder=str(query.folder),
            ),
        )
        if not confirmed:
            return
        # Files with unsaved changes in Forge are skipped: their tab wins.
        dirty = {e.path for e in self._api.editors() if e.is_dirty and e.path is not None}
        replacement = self.replace_edit.text()
        pattern = query.compile()
        self.status.setText(tr("Replacing..."))
        self._set_busy(True)
        self._cancel.clear()
        bridge = self._bridge
        cancel = self._cancel

        def work() -> None:
            totals = {"count": 0, "files": 0, "skipped": 0}
            matched: list[FileResult] = []
            try:
                search(query, cancel, matched.append)
                for result in matched:
                    if cancel.is_set():
                        break
                    if result.path in dirty:
                        totals["skipped"] += 1
                        continue
                    count = replace_in_file(result.path, pattern, replacement, query.regex)
                    if count:
                        totals["count"] += count
                        totals["files"] += 1
            except Exception as exc:
                bridge.failed.emit(str(exc))
                return
            bridge.finished.emit(totals)

        self._bridge.finished.disconnect()
        self._bridge.finished.connect(self._replaced)
        self._thread = threading.Thread(target=work, name="forge-replace-in-files", daemon=True)
        self._thread.start()

    def _replaced(self, totals: dict[str, int]) -> None:
        self._bridge.finished.disconnect()
        self._bridge.finished.connect(self._finished)
        self._set_busy(False)
        self.results.clear()
        text = tr(
            "{count} replaced in {files} files.", count=totals["count"], files=totals["files"]
        )
        if totals["skipped"]:
            text += " " + tr(
                "{skipped} files with unsaved changes were skipped.", skipped=totals["skipped"]
            )
        self.status.setText(text)


def open_panel(api: ForgeAPI) -> None:
    panel = api.panel("find-in-files", tr("Find in Files"), lambda: FindInFilesPanel(api))
    if isinstance(panel, FindInFilesPanel):
        panel.prepare()

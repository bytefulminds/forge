"""Lazy JSON tree: children are created only when a node is expanded."""

from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget

from forge.i18n.translator import tr

_PLACEHOLDER = "…"
_VALUE_ROLE = 256  # Qt.ItemDataRole.UserRole
_PATH_ROLE = 257


def type_name(value: Any) -> str:
    if isinstance(value, dict):
        return tr("object ({count})", count=len(value))
    if isinstance(value, list):
        return tr("array ({count})", count=len(value))
    if isinstance(value, str):
        return tr("string")
    if isinstance(value, bool):
        return tr("boolean")
    if value is None:
        return "null"
    return tr("number")


def preview(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return ""
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 200 else text[:200] + _PLACEHOLDER


class JsonTree(QTreeWidget):
    # Path of the clicked item: object keys (str) and array indexes (int).
    path_clicked = pyqtSignal(tuple)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("jsonTree")
        self.setHeaderLabels([tr("Key"), tr("Value"), tr("Type")])
        self.setUniformRowHeights(True)
        self.itemExpanded.connect(self._expand)
        self.itemClicked.connect(self._clicked)
        self.itemActivated.connect(self._clicked)

    @staticmethod
    def path_of(item: QTreeWidgetItem) -> tuple[str | int, ...]:
        path = item.data(0, _PATH_ROLE)
        return tuple(path) if path else ()

    def _clicked(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        if item.text(0) != _PLACEHOLDER:
            self.path_clicked.emit(self.path_of(item))

    def show_data(self, data: Any) -> None:
        self.clear()
        root = self._item(None, "(root)", data, ())
        self.addTopLevelItem(root)
        root.setExpanded(True)
        self.resizeColumnToContents(0)

    def _item(
        self,
        parent: QTreeWidgetItem | None,
        key: str,
        value: Any,
        path: tuple[str | int, ...],
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([key, preview(value), type_name(value)])
        item.setData(0, _VALUE_ROLE, value)
        item.setData(0, _PATH_ROLE, list(path))
        if parent is not None:
            parent.addChild(item)
        if isinstance(value, (dict, list)) and value:
            item.addChild(QTreeWidgetItem([_PLACEHOLDER]))
        return item

    def _expand(self, item: QTreeWidgetItem) -> None:
        first = item.child(0)
        if item.childCount() != 1 or first is None or first.text(0) != _PLACEHOLDER:
            return
        item.takeChild(0)
        value = item.data(0, _VALUE_ROLE)
        path = self.path_of(item)
        if isinstance(value, dict):
            for key, child in value.items():
                self._item(item, str(key), child, (*path, str(key)))
        else:
            for index, child in enumerate(value):
                self._item(item, f"[{index}]", child, (*path, index))

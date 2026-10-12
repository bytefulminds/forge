"""Encoding and line ending menus, shared by the menu bar and the status bar."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QMenu, QWidget

from forge.core.encoding import MENU_ENCODINGS, TextEncoding
from forge.core.eol import Eol
from forge.i18n.translator import tr


class EolMenu(QMenu):
    """Edit > EOL Conversion, as in Notepad++."""

    eol_chosen = pyqtSignal(object)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        group = QActionGroup(self)
        self._actions: dict[Eol, QAction] = {}
        labels = {
            Eol.CRLF: tr("Windows (CR LF)"),
            Eol.LF: tr("Unix (LF)"),
            Eol.CR: tr("Macintosh (CR)"),
        }
        for eol in (Eol.CRLF, Eol.LF, Eol.CR):
            action = QAction(labels[eol], group)
            action.setCheckable(True)
            action.setMenuRole(QAction.MenuRole.NoRole)
            action.triggered.connect(lambda _c=False, e=eol: self.eol_chosen.emit(e))
            self.addAction(action)
            self._actions[eol] = action

    def set_current(self, eol: Eol) -> None:
        self._actions[eol].setChecked(True)


class EncodingMenu(QMenu):
    """Encoding menu, as in Notepad++.

    The upper items reinterpret the file on disk in another encoding (the text
    may change, the file does not). "Convert to" keeps the text and changes the
    encoding used when saving.
    """

    reinterpret_chosen = pyqtSignal(object)
    convert_chosen = pyqtSignal(object)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        group = QActionGroup(self)
        self._actions: dict[TextEncoding, QAction] = {}
        for encoding in MENU_ENCODINGS:
            action = QAction(encoding.label, group)
            action.setCheckable(True)
            action.setMenuRole(QAction.MenuRole.NoRole)
            action.setToolTip(
                tr("Reload the file from disk as {encoding}", encoding=encoding.label)
            )
            action.triggered.connect(lambda _c=False, e=encoding: self.reinterpret_chosen.emit(e))
            self.addAction(action)
            self._actions[encoding] = action
        self.addSeparator()
        for encoding in MENU_ENCODINGS:
            action = QAction(tr("Convert to {encoding}", encoding=encoding.label), self)
            action.setMenuRole(QAction.MenuRole.NoRole)
            action.triggered.connect(lambda _c=False, e=encoding: self.convert_chosen.emit(e))
            self.addAction(action)
        self.setToolTipsVisible(True)

    def set_current(self, encoding: TextEncoding) -> None:
        action = self._actions.get(encoding)
        if action is not None:
            action.setChecked(True)
        else:
            for other in self._actions.values():
                other.setChecked(False)

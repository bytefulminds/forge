"""XML Tools commands."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI, tr
from forge.tools.xml_tool.core import XmlError, pretty, xpath
from forge.tools.xml_tool.core import minify as minify_text


def _report(api: ForgeAPI, error: XmlError) -> None:
    editor = api.active_editor()
    if editor is None:
        return
    api.show_error_at(
        editor,
        tr(
            "XML error at line {line}, column {column}: {error}",
            line=error.line,
            column=error.column,
            error=error.message,
        ),
        error.line,
        error.column,
    )


def pretty_print(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None:
        return
    text = editor.text()
    eol = "\r\n" if "\r\n" in text else "\n"
    try:
        result = pretty(text, editor.indent_unit(), eol)
    except XmlError as error:
        _report(api, error)
        return
    editor.set_text(result)
    if editor.language_id == "text":
        editor.set_language("xml")
    api.status(tr("XML formatted."))


def minify(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None:
        return
    try:
        result = minify_text(editor.text())
    except XmlError as error:
        _report(api, error)
        return
    editor.set_text(result)
    api.status(tr("XML minified."))


def check(api: ForgeAPI) -> None:
    editor = api.active_editor()
    if editor is None:
        return
    try:
        pretty(editor.text(), "  ")
    except XmlError as error:
        _report(api, error)
        return
    api.notify(tr("The document is well-formed XML."), "info")


class XPathPanel(QWidget):
    def __init__(self, api: ForgeAPI) -> None:
        super().__init__()
        self.setObjectName("toolPanel")
        self._api = api
        self.expression = QLineEdit(self)
        self.expression.setPlaceholderText(tr("XPath expression, for example //item[@id]"))
        self.expression.setText(str(api.setting("last_xpath", "") or ""))
        self.expression.returnPressed.connect(self.evaluate)
        run = QPushButton(tr("Evaluate"), self)
        run.setProperty("primary", "true")
        run.clicked.connect(self.evaluate)
        self.summary = QLabel(self)
        self.results = QListWidget(self)
        self.results.itemActivated.connect(self._jump)
        self.results.itemClicked.connect(self._jump)
        top = QHBoxLayout()
        top.addWidget(self.expression, 1)
        top.addWidget(run)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addLayout(top)
        layout.addWidget(self.summary)
        layout.addWidget(self.results)

    def evaluate(self) -> None:
        editor = self._api.active_editor()
        expression = self.expression.text().strip()
        self.results.clear()
        if editor is None or not expression:
            return
        self._api.set_setting("last_xpath", expression)
        try:
            found = xpath(editor.text(), expression)
        except XmlError as error:
            self.summary.setText(tr("Error: {error}", error=error.message))
            return
        self.summary.setText(tr("{count} results", count=len(found)))
        for description, line in found:
            label = f"{line}: {description}" if line else description
            item = QListWidgetItem(label)
            item.setData(256, line)
            self.results.addItem(item)

    def _jump(self, item: QListWidgetItem) -> None:
        line = item.data(256)
        editor = self._api.active_editor()
        if editor is not None and line:
            editor.go_to(int(line))


def show_xpath(api: ForgeAPI) -> None:
    panel = api.panel("xml-xpath", tr("XPath"), lambda: XPathPanel(api))
    if isinstance(panel, XPathPanel):
        panel.expression.setFocus()
        panel.expression.selectAll()

"""Interactive windows of the developer tools (UUIDs, date converter, cron)."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from forge.extensions.api import ForgeAPI
from forge.i18n.translator import tr
from forge.tools.devtools import cron, datetimes, uuids

_MONO = "JetBrains Mono"


def day_names() -> list[str]:
    return [
        tr("Sunday"), tr("Monday"), tr("Tuesday"), tr("Wednesday"),
        tr("Thursday"), tr("Friday"), tr("Saturday"),
    ]  # fmt: skip


def month_names() -> list[str]:
    return [
        tr("January"), tr("February"), tr("March"), tr("April"), tr("May"), tr("June"),
        tr("July"), tr("August"), tr("September"), tr("October"), tr("November"),
        tr("December"),
    ]  # fmt: skip


def _close_buttons(parent: QWidget) -> QDialogButtonBox:
    return QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent)


class UuidDialog:
    """Count and format for Insert UUIDs; ``exec()`` and ``options()``."""

    def __init__(self, api: ForgeAPI) -> None:
        self.dialog = api.framed_dialog(tr("Insert UUIDs"))
        self.DialogCode = self.dialog.DialogCode
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 16, 22, 14)
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        self.count = QSpinBox(body)
        self.count.setRange(1, 10_000)
        self.count.setValue(5)
        self.version = QComboBox(body)
        self.version.addItem(tr("Version 4 (random)"), 4)
        self.version.addItem(tr("Version 7 (time ordered)"), 7)
        self.separator = QComboBox(body)
        self.separator.addItem(tr("One per line"), "\n")
        self.separator.addItem(tr("Comma separated"), ", ")
        self.uppercase = QCheckBox(tr("Uppercase"), body)
        self.hyphens = QCheckBox(tr("With hyphens"), body)
        self.hyphens.setChecked(True)
        self.braces = QCheckBox(tr("In braces {...} (Windows GUID)"), body)
        self.preview = QLabel(body)
        self.preview.setFont(QFont(_MONO))
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(tr("Number"), self.count)
        form.addRow(tr("Kind"), self.version)
        form.addRow(tr("Layout"), self.separator)
        form.addRow("", self.uppercase)
        form.addRow("", self.hyphens)
        form.addRow("", self.braces)
        form.addRow(tr("Example"), self.preview)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, body
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Insert"))
            ok.setDefault(True)
        buttons.accepted.connect(self.dialog.accept)
        buttons.rejected.connect(self.dialog.reject)
        layout.addWidget(buttons)
        for box in (self.uppercase, self.hyphens, self.braces):
            box.toggled.connect(self._update)
        self.version.currentIndexChanged.connect(self._update)
        self._update()

    def options(self) -> uuids.UuidOptions:
        return uuids.UuidOptions(
            count=self.count.value(),
            version=int(self.version.currentData()),
            uppercase=self.uppercase.isChecked(),
            hyphens=self.hyphens.isChecked(),
            braces=self.braces.isChecked(),
            separator=str(self.separator.currentData()),
        )

    def _update(self) -> None:
        example = uuids.UuidOptions(
            version=int(self.version.currentData()),
            uppercase=self.uppercase.isChecked(),
            hyphens=self.hyphens.isChecked(),
            braces=self.braces.isChecked(),
        )
        self.preview.setText(uuids.generate(example))

    def exec(self) -> int:
        return self.dialog.exec()


class DateTimeDialog:
    """Type a timestamp or a date and see it in every common notation."""

    def __init__(self, api: ForgeAPI, value: str) -> None:
        self._api = api
        self.dialog = api.framed_dialog(tr("Date and Time Converter"), resizable=True)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 16, 22, 14)
        layout.setSpacing(12)
        hint = QLabel(
            tr('A Unix timestamp (s, ms, us, ns), an ISO 8601 or RFC 2822 date, or "now".'),
            body,
        )
        hint.setObjectName("resultNote")
        hint.setWordWrap(True)
        self.input = QLineEdit(value, body)
        self.input.setFont(QFont(_MONO))
        self.error = QLabel(body)
        self.error.setObjectName("prefNote")
        self.error.hide()
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.outputs: dict[str, QLineEdit] = {}
        for row, (name, _value) in enumerate(
            datetimes.conversions(datetime.now().astimezone(), tr)
        ):
            label = QLabel(name, body)
            field = QLineEdit(body)
            field.setReadOnly(True)
            field.setFont(QFont(_MONO))
            copy = api.copy_button(body, field.text)
            grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(field, row, 1)
            grid.addWidget(copy, row, 2)
            self.outputs[name] = field
        grid.setColumnStretch(1, 1)
        buttons = _close_buttons(body)
        buttons.rejected.connect(self.dialog.reject)
        layout.addWidget(hint)
        layout.addWidget(self.input)
        layout.addWidget(self.error)
        layout.addLayout(grid)
        layout.addWidget(buttons)
        self.input.textChanged.connect(self._update)
        self._update()
        self.dialog.resize(620, self.dialog.sizeHint().height())

    def _update(self) -> None:
        try:
            moment = datetimes.parse_moment(self.input.text())
        except ValueError:
            self.error.setText(tr("Not a timestamp or a date."))
            self.error.show()
            for field in self.outputs.values():
                field.clear()
            return
        self.error.hide()
        for name, value in datetimes.conversions(moment, tr):
            if name in self.outputs:
                self.outputs[name].setText(value)

    def exec(self) -> int:
        return self.dialog.exec()


class CronDialog:
    """Explain a cron expression and list its next run times."""

    RUNS = 10

    def __init__(self, api: ForgeAPI, expression: str) -> None:
        self.dialog = api.framed_dialog(tr("Explain Cron Expression"), resizable=True)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 16, 22, 14)
        layout.setSpacing(10)
        hint = QLabel(tr("minute  hour  day-of-month  month  day-of-week"), body)
        hint.setObjectName("resultNote")
        hint.setFont(QFont(_MONO))
        self.input = QLineEdit(expression, body)
        self.input.setFont(QFont(_MONO))
        self.summary = QLabel(body)
        self.summary.setObjectName("cronSummary")
        self.summary.setWordWrap(True)
        runs_label = QLabel(tr("Next runs (local time)"), body)
        runs_label.setObjectName("prefSection")
        self.runs = QPlainTextEdit(body)
        self.runs.setReadOnly(True)
        self.runs.setFont(QFont(_MONO))
        self.runs.setMinimumHeight(200)
        buttons = _close_buttons(body)
        buttons.rejected.connect(self.dialog.reject)
        for widget in (hint, self.input, self.summary, runs_label, self.runs, buttons):
            layout.addWidget(widget)
        self.input.textChanged.connect(self._update)
        self._update()
        self.dialog.resize(560, self.dialog.sizeHint().height())

    def _update(self) -> None:
        try:
            parsed = cron.parse(self.input.text())
        except cron.CronError as exc:
            self.summary.setText(tr("Not valid: {reason}", reason=str(exc)))
            self.runs.setPlainText("")
            return
        self.summary.setText(cron.describe(parsed, tr, day_names(), month_names()))
        now = datetime.now()
        lines = [
            run.strftime("%Y-%m-%d %H:%M") + f"   {day_names()[run.isoweekday() % 7]}"
            for run in parsed.next_runs(now, self.RUNS)
        ]
        self.runs.setPlainText("\n".join(lines) or tr("No run in the next five years."))

    def exec(self) -> int:
        return self.dialog.exec()

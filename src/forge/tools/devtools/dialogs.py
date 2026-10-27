"""Interactive windows of the developer tools (UUIDs, date converter, cron)."""

from __future__ import annotations

from datetime import UTC, datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
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


def _cheat_sheet() -> list[tuple[str, str, str]]:
    """(symbol, meaning, example) rows; clicking a row loads its example."""
    return [
        ("*", tr("Any value"), "* * * * *"),
        ("-", tr("Range of values"), "1-10 * * * *"),
        (",", tr("List of values"), "1,10 * * * *"),
        ("/", tr("Step values"), "*/10 * * * *"),
        ("@yearly", tr("1 January at 00:00 (also @annually)"), "@yearly"),
        ("@monthly", tr("The first of the month at 00:00"), "@monthly"),
        ("@weekly", tr("Sunday at 00:00"), "@weekly"),
        ("@daily", tr("Every day at 00:00 (also @midnight)"), "@daily"),
        ("@hourly", tr("Every hour, on the hour"), "@hourly"),
        ("@reboot", tr("Once, when the system starts"), "@reboot"),
    ]


def _field_label(kind: str) -> str:
    return {
        cron.SECOND: tr("Second"),
        cron.MINUTE: tr("Minute"),
        cron.HOUR: tr("Hour"),
        cron.DAY: tr("Day of month"),
        cron.MONTH: tr("Month"),
        cron.WEEKDAY: tr("Day of week"),
    }[kind]


def _field_range(kind: str) -> str:
    return {
        cron.SECOND: "0-59",
        cron.MINUTE: "0-59",
        cron.HOUR: "0-23",
        cron.DAY: "1-31",
        cron.MONTH: tr("1-12 or JAN-DEC"),
        cron.WEEKDAY: tr("0-6 or SUN-SAT"),
    }[kind]


def _fit_columns(tree: QTreeWidget, stretch: int) -> None:
    """Columns as wide as their content, one taking the rest: no side scrolling."""
    header = tree.header()
    if header is None:
        return
    header.setStretchLastSection(False)
    for column in range(tree.columnCount()):
        mode = (
            QHeaderView.ResizeMode.Stretch
            if column == stretch
            else (QHeaderView.ResizeMode.ResizeToContents)
        )
        header.setSectionResizeMode(column, mode)
    tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class _FieldCard(QFrame):
    """One field of the expression: its text, name and meaning."""

    def __init__(self, kind: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName("cronField")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        self.token = QLabel(self)
        self.token.setObjectName("cronFieldToken")
        self.token.setFont(QFont(_MONO))
        self.name = QLabel(_field_label(kind), self)
        self.name.setObjectName("cronFieldName")
        self.meaning = QLabel(self)
        self.meaning.setObjectName("cronFieldMeaning")
        self.meaning.setWordWrap(True)
        for label in (self.token, self.name, self.meaning):
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(label)
        layout.addStretch(1)
        self.setToolTip(_field_range(kind))

    def show_field(self, text: str, meaning: str, invalid: bool) -> None:
        self.token.setText(text)
        self.meaning.setText(meaning)
        self.setProperty("invalid", invalid)
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)


class CronDialog:
    """Write or check a cron expression: what it means, per field, its next
    run times, and a cheat sheet whose examples load with one click."""

    RUNS = 10

    def __init__(self, api: ForgeAPI, line: str, replace: bool = False) -> None:
        self._api = api
        self._replace = replace
        schedule, self.command = cron.split_line(line)
        self.dialog = api.framed_dialog(tr("Cron Expression"), resizable=True)
        body = self.dialog.body
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 18, 24, 14)
        layout.setSpacing(10)

        self.input = QLineEdit(schedule, body)
        self.input.setObjectName("cronInput")
        self.input.setFont(QFont(_MONO))
        self.input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input.setPlaceholderText("* * * * *")
        self.input.setMaximumWidth(560)
        centered = QHBoxLayout()
        centered.addStretch(1)
        centered.addWidget(self.input, 4)
        centered.addStretch(1)
        self.summary = QLabel(body)
        self.summary.setObjectName("cronSummary")
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.error = QLabel(body)
        self.error.setObjectName("cronError")
        self.error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error.setWordWrap(True)
        self.command_label = QLabel(body)
        self.command_label.setObjectName("resultNote")
        self.command_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.command_label.setFont(QFont(_MONO))

        cards = QHBoxLayout()
        cards.setSpacing(8)
        self.cards = {
            kind: _FieldCard(kind, body)
            for kind in (cron.SECOND, cron.MINUTE, cron.HOUR, cron.DAY, cron.MONTH, cron.WEEKDAY)
        }
        for card in self.cards.values():
            cards.addWidget(card, 1)

        panels = QHBoxLayout()
        panels.setSpacing(16)
        panels.addLayout(self._runs_panel(body), 4)
        panels.addLayout(self._cheat_panel(body), 5)

        buttons = QDialogButtonBox(body)
        copy = buttons.addButton(tr("Copy"), QDialogButtonBox.ButtonRole.ActionRole)
        use = buttons.addButton(
            tr("Replace Selection") if replace else tr("Insert"),
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        assert copy is not None and use is not None and close is not None
        self.use_button = use
        copy.clicked.connect(lambda: api.copy_to_clipboard(self.line()))
        use.clicked.connect(self._use)
        close.clicked.connect(self.dialog.reject)
        use.setEnabled(api.active_editor() is not None)

        layout.addLayout(centered)
        layout.addWidget(self.summary)
        layout.addWidget(self.error)
        layout.addWidget(self.command_label)
        layout.addLayout(cards)
        layout.addLayout(panels, 1)
        layout.addWidget(buttons)

        self.input.textChanged.connect(self._update)
        self._update()
        self.dialog.resize(940, 640)

    # Panels ------------------------------------------------------------------------

    def _runs_panel(self, body: QWidget) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(6)
        header = QHBoxLayout()
        title = QLabel(tr("Next runs"), body)
        title.setObjectName("cronSection")
        self.zone = QComboBox(body)
        self.zone.addItem(tr("Local time"), False)
        self.zone.addItem(tr("UTC"), True)
        self.zone.setCurrentIndex(1 if self._api.setting("utc", False) else 0)
        self.clock24 = QCheckBox(tr("24-hour clock"), body)
        self.clock24.setChecked(bool(self._api.setting("clock24", True)))
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.zone)
        header.addWidget(self.clock24)
        self.runs = QTreeWidget(body)
        self.runs.setObjectName("cronRuns")
        self.runs.setRootIsDecorated(False)
        self.runs.setColumnCount(4)
        self.runs.setHeaderLabels([tr("Date"), tr("Day"), tr("Time"), tr("From now")])
        self.runs.setFont(QFont(_MONO))
        self.runs.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.runs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        panel.addLayout(header)
        panel.addWidget(self.runs, 1)
        self.zone.currentIndexChanged.connect(self._options_changed)
        self.clock24.toggled.connect(self._options_changed)
        return panel

    def _cheat_panel(self, body: QWidget) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(6)
        header = QHBoxLayout()
        title = QLabel(tr("Cheat sheet"), body)
        title.setObjectName("cronSection")
        hint = QLabel(tr("Click a row to try it"), body)
        hint.setObjectName("resultNote")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(hint)
        self.cheat = QTreeWidget(body)
        self.cheat.setObjectName("cronCheatSheet")
        self.cheat.setRootIsDecorated(False)
        self.cheat.setColumnCount(3)
        self.cheat.setHeaderLabels([tr("Symbol"), tr("Meaning"), tr("Example")])
        self.cheat.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        mono = QFont(_MONO)
        for symbol, meaning, example in _cheat_sheet():
            item = QTreeWidgetItem([symbol, meaning, example])
            item.setFont(0, mono)
            item.setFont(2, mono)
            item.setData(0, Qt.ItemDataRole.UserRole, example)
            if example.startswith("@"):
                item.setToolTip(2, cron.SHORTCUTS.get(example, ""))
            self.cheat.addTopLevelItem(item)
        _fit_columns(self.cheat, stretch=1)
        viewport = self.cheat.viewport()
        if viewport is not None:
            viewport.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cheat.itemClicked.connect(self._try_example)
        panel.addLayout(header)
        panel.addWidget(self.cheat, 1)
        return panel

    # Behavior ----------------------------------------------------------------------

    def line(self) -> str:
        schedule = self.input.text().strip()
        return f"{schedule} {self.command}" if self.command else schedule

    def _try_example(self, item: QTreeWidgetItem, _column: int) -> None:
        self.input.setText(str(item.data(0, Qt.ItemDataRole.UserRole)))

    def _options_changed(self) -> None:
        self._api.set_setting("utc", bool(self.zone.currentData()))
        self._api.set_setting("clock24", self.clock24.isChecked())
        self._update()

    def _use(self) -> None:
        editor = self._api.active_editor()
        if editor is None or editor.widget.isReadOnly():
            return
        text = self.line()
        if self._replace and editor.has_selection():
            editor.replace_selection_and_select(text, 0, len(text))
        else:
            editor.insert(text)
        self.dialog.accept()

    def _update(self) -> None:
        text = self.input.text()
        self.command_label.setText(tr("Command: {command}", command=self.command))
        self.command_label.setVisible(bool(self.command))
        clock24 = self.clock24.isChecked()
        self.runs.clear()
        if cron.is_reboot(text):
            self._show_cards([])
            self._show_result(tr("Once, when the system starts"), "")
            return
        try:
            fields = cron.split(text)
        except cron.CronError as exc:
            self._show_cards([])
            self._show_result("", tr("Not valid: {reason}", reason=str(exc)))
            return
        self._show_cards(fields)
        try:
            parsed = cron.parse(text)
        except cron.CronError as exc:
            self._show_result("", tr("Not valid: {reason}", reason=str(exc)))
            return
        self._show_result(
            cron.describe(parsed, tr, day_names(), month_names(), clock24),
            "",
        )
        self._fill_runs(parsed, clock24)

    def _show_result(self, summary: str, error: str) -> None:
        self.summary.setText(summary)
        self.summary.setVisible(bool(summary))
        self.error.setText(error)
        self.error.setVisible(bool(error))
        self.input.setProperty("invalid", bool(error))
        style = self.input.style()
        if style is not None:
            style.unpolish(self.input)
            style.polish(self.input)

    def _show_cards(self, fields: list[tuple[str, str]]) -> None:
        given = dict(fields)
        for kind, card in self.cards.items():
            if kind not in given:
                # Seconds only for six fields; empty cards while the count is wrong.
                card.setVisible(kind != cron.SECOND)
                card.show_field("", "", False)
                continue
            card.setVisible(True)
            try:
                field = cron.parse_field(given[kind], kind)
            except cron.CronError as exc:
                card.show_field(given[kind], str(exc), True)
                continue
            meaning = cron.field_meaning(kind, field, tr, day_names(), month_names())
            card.show_field(given[kind], meaning, False)

    def _fill_runs(self, parsed: cron.Cron, clock24: bool) -> None:
        utc = bool(self.zone.currentData())
        now = datetime.now(UTC) if utc else datetime.now()
        names = day_names()
        runs = parsed.next_runs(now, self.RUNS)
        for run in runs:
            seconds = run.second if parsed.second is not None else None
            aware = run if utc else run.astimezone()
            item = QTreeWidgetItem(
                [
                    run.strftime("%Y-%m-%d"),
                    names[run.isoweekday() % 7],
                    cron.clock(run.hour, run.minute, clock24, seconds),
                    datetimes.relative(aware, tr),
                ]
            )
            self.runs.addTopLevelItem(item)
        if not runs:
            self.runs.addTopLevelItem(QTreeWidgetItem([tr("No run in the next five years.")]))
        _fit_columns(self.runs, stretch=3)

    def exec(self) -> int:
        return self.dialog.exec()

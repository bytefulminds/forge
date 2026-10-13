"""CSV tools: delimiter, align, sort, duplicates, timestamps and export."""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo
from forge.i18n.translator import tr

_ACTIONS = "forge.tools.csv_tool.actions"
_CSV = ("csv",)

EXTENSION = ExtensionInfo(
    id="forge.csv",
    title=lambda: tr("&CSV"),
    commands=(
        CommandSpec(
            "csv.delimiter",
            lambda: tr("&Delimiter..."),
            f"{_ACTIONS}:choose_delimiter",
            languages=_CSV,
            icon="separator-vertical",
            tooltip=lambda: tr("Delimiter used to read this file"),
        ),
        CommandSpec(
            "csv.header",
            lambda: tr("&Header Row..."),
            f"{_ACTIONS}:choose_header",
            languages=_CSV,
            icon="panel-top",
            tooltip=lambda: tr("Whether the first row holds the column names"),
        ),
        CommandSpec(
            "csv.convert_delimiter",
            lambda: tr("C&onvert Delimiter..."),
            f"{_ACTIONS}:convert_delimiter",
            languages=_CSV,
            icon="replace",
            tooltip=lambda: tr("Rewrite the file with another delimiter"),
        ),
        CommandSpec(
            "csv.align",
            lambda: tr("&Align Columns"),
            f"{_ACTIONS}:align_columns",
            separator_before=True,
            languages=_CSV,
            icon="align-left",
        ),
        CommandSpec(
            "csv.shrink",
            lambda: tr("&Shrink Columns"),
            f"{_ACTIONS}:shrink_columns",
            languages=_CSV,
            icon="fold-horizontal",
            tooltip=lambda: tr("Remove the spaces around cells"),
        ),
        CommandSpec(
            "csv.sort_asc",
            lambda: tr("Sort As&cending"),
            f"{_ACTIONS}:sort_ascending",
            separator_before=True,
            languages=_CSV,
            icon="arrow-down-a-z",
            tooltip=lambda: tr("Sort rows by the column at the cursor, A to Z"),
        ),
        CommandSpec(
            "csv.sort_desc",
            lambda: tr("Sort Desce&nding"),
            f"{_ACTIONS}:sort_descending",
            languages=_CSV,
            icon="arrow-down-z-a",
            tooltip=lambda: tr("Sort rows by the column at the cursor, Z to A"),
        ),
        CommandSpec(
            "csv.dedupe",
            lambda: tr("Remove D&uplicate Rows"),
            f"{_ACTIONS}:remove_duplicates",
            languages=_CSV,
            icon="copy-minus",
        ),
        CommandSpec(
            "csv.epoch_to_iso",
            lambda: tr("&Epoch to ISO 8601"),
            f"{_ACTIONS}:epoch_to_iso",
            separator_before=True,
            languages=_CSV,
            icon="calendar-clock",
            tooltip=lambda: tr(
                "Unix timestamps to ISO 8601 dates (the selection, or the column at the cursor)"
            ),
        ),
        CommandSpec(
            "csv.iso_to_epoch",
            lambda: tr("&ISO 8601 to Epoch"),
            f"{_ACTIONS}:iso_to_epoch",
            languages=_CSV,
            icon="hash",
            tooltip=lambda: tr(
                "ISO 8601 dates to Unix timestamps (the selection, or the column at the cursor)"
            ),
        ),
        CommandSpec(
            "csv.local_time",
            lambda: tr("Use &Local Time"),
            f"{_ACTIONS}:setting_changed",
            checked_setting="local_time",
        ),
        CommandSpec(
            "csv.epoch_ms",
            lambda: tr("Epoch in &Milliseconds"),
            f"{_ACTIONS}:setting_changed",
            checked_setting="epoch_ms",
        ),
        CommandSpec(
            "csv.to_json",
            lambda: tr("Convert to &JSON"),
            f"{_ACTIONS}:to_json",
            separator_before=True,
            languages=_CSV,
            icon="braces",
            tooltip=lambda: tr("Open the data as JSON in a new tab"),
        ),
        CommandSpec(
            "csv.to_markdown",
            lambda: tr("Convert to Mar&kdown Table"),
            f"{_ACTIONS}:to_markdown",
            languages=_CSV,
            icon="table-2",
            tooltip=lambda: tr("Open the data as a Markdown table in a new tab"),
        ),
    ),
    defaults={"local_time": False, "epoch_ms": False},
)

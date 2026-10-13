"""Developer tools in the Tools menu (and the editor's right-click menu):
hashes, encodings, letter case and lines, UUIDs, date and time, cron.

Each group is its own extension, so adding a tool is one CommandSpec here
and one function in ``actions``.
"""

from __future__ import annotations

from forge.extensions.base import CommandSpec, ExtensionInfo, Text
from forge.i18n.translator import tr

_A = "forge.tools.devtools.actions"


def _cmd(
    id: str, title: Text, handler: str, context: str | None = "selection", sep: bool = False
) -> CommandSpec:
    return CommandSpec(id, title, f"{_A}:{handler}", context=context, separator_before=sep)


HASH = ExtensionInfo(
    id="forge.hash",
    title=lambda: tr("&Hash"),
    separator_before=True,
    commands=(
        _cmd("hash.text", lambda: tr("Hash &Selection..."), "hash_selection", "always"),
        _cmd("hash.files", lambda: tr("Hash &Files..."), "hash_files", None),
    ),
)

ENCODE = ExtensionInfo(
    id="forge.encode",
    title=lambda: tr("&Encode / Decode"),
    commands=(
        _cmd("encode.base64", lambda: tr("Base64 &Encode"), "base64_encode"),
        _cmd("decode.base64", lambda: tr("Base64 &Decode"), "base64_decode"),
        _cmd("encode.url", lambda: tr("&URL Encode"), "url_encode", sep=True),
        _cmd("decode.url", lambda: tr("URL Dec&ode"), "url_decode"),
        _cmd("encode.html", lambda: tr("&HTML Escape"), "html_escape", sep=True),
        _cmd("decode.html", lambda: tr("HTML U&nescape"), "html_unescape"),
        _cmd("encode.json", lambda: tr("&JSON String Escape"), "json_escape", sep=True),
        _cmd("decode.json", lambda: tr("JSON String Unesca&pe"), "json_unescape"),
        _cmd("decode.jwt", lambda: tr("Decode JW&T"), "decode_jwt", sep=True),
    ),
)

TEXT = ExtensionInfo(
    id="forge.text",
    title=lambda: tr("&Text"),
    commands=(
        _cmd("case.upper", lambda: tr("&UPPERCASE"), "upper_case"),
        _cmd("case.lower", lambda: tr("&lowercase"), "lower_case"),
        _cmd("case.title", lambda: tr("&Title Case"), "title_case"),
        _cmd("case.camel", lambda: tr("&camelCase"), "camel_case", sep=True),
        _cmd("case.pascal", lambda: tr("&PascalCase"), "pascal_case"),
        _cmd("case.snake", lambda: tr("&snake_case"), "snake_case"),
        _cmd("case.kebab", lambda: tr("&kebab-case"), "kebab_case"),
        _cmd("lines.sort", lambda: tr("Sort Lines &Ascending"), "sort_lines_ascending", sep=True),
        _cmd("lines.sort_desc", lambda: tr("Sort Lines &Descending"), "sort_lines_descending"),
        _cmd("lines.unique", lambda: tr("Remove Dupl&icate Lines"), "unique_lines"),
        _cmd("lines.reverse", lambda: tr("&Reverse Lines"), "reverse_lines"),
        _cmd("lines.trim", lambda: tr("Trim Trailing &Whitespace"), "trim_trailing"),
    ),
)

GENERATE = ExtensionInfo(
    id="forge.generate",
    title=lambda: tr("&Generate"),
    commands=(
        _cmd("generate.uuid", lambda: tr("Insert &UUID"), "insert_uuid", "always"),
        _cmd("generate.uuids", lambda: tr("Insert UUIDs..."), "insert_uuids", "always"),
    ),
)

DATETIME = ExtensionInfo(
    id="forge.datetime",
    title=lambda: tr("&Date and Time"),
    commands=(
        _cmd("datetime.now", lambda: tr("Insert &Date and Time"), "insert_now", "always"),
        _cmd(
            "datetime.now_utc",
            lambda: tr("Insert Date and Time (&UTC)"),
            "insert_now_utc",
            "always",
        ),
        _cmd("datetime.today", lambda: tr("Insert D&ate"), "insert_today", "always"),
        _cmd("datetime.epoch", lambda: tr("Insert Unix &Timestamp"), "insert_epoch", "always"),
        _cmd("datetime.to_iso", lambda: tr("&Epoch to ISO 8601"), "epoch_to_iso", sep=True),
        _cmd("datetime.to_epoch", lambda: tr("&ISO 8601 to Epoch"), "iso_to_epoch"),
        _cmd(
            "datetime.convert",
            lambda: tr("Date and Time &Converter..."),
            "converter",
            "always",
            sep=True,
        ),
    ),
)

CRON = ExtensionInfo(
    id="forge.cron",
    title=lambda: tr("C&ron"),
    commands=(
        _cmd("cron.explain", lambda: tr("&Explain Cron Expression..."), "explain_cron", "always"),
    ),
)

EXTENSIONS = (HASH, ENCODE, TEXT, GENERATE, DATETIME, CRON)

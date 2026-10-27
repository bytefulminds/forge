"""Cheap checks on the selected text, so the right-click menu only offers
the conversions that make sense for it (no Qt, stdlib only)."""

from __future__ import annotations

import re

from forge.core.timestamps import convert_in_text

_MAX = 200_000  # longer selections are not inspected
_BASE64 = re.compile(r"^[A-Za-z0-9+/_-]+={0,2}$")
_PERCENT = re.compile(r"%[0-9A-Fa-f]{2}")
_ENTITY = re.compile(r"&(#\d+|#x[0-9A-Fa-f]+|[A-Za-z]+);")
_ESCAPE = re.compile(r'\\["\\/bfnrtu]')
_JWT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*$")
_CRON_FIELD = re.compile(r"^[\d*/,\-A-Za-z?]+$")


def looks_like_base64(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 4 or len(text) > _MAX or not _BASE64.match(compact):
        return False
    from forge.tools.devtools.transforms import base64_decode

    try:
        base64_decode(compact)
    except ValueError:
        return False
    return True


def has_percent_escapes(text: str) -> bool:
    return len(text) <= _MAX and bool(_PERCENT.search(text))


def has_html_entities(text: str) -> bool:
    return len(text) <= _MAX and bool(_ENTITY.search(text))


def has_json_escapes(text: str) -> bool:
    return len(text) <= _MAX and bool(_ESCAPE.search(text))


def looks_like_jwt(text: str) -> bool:
    return len(text) <= _MAX and bool(_JWT.match(text.strip())) and text.strip().startswith("ey")


def has_epoch(text: str) -> bool:
    return len(text) <= _MAX and convert_in_text(text, True)[1] > 0


def has_iso_date(text: str) -> bool:
    return len(text) <= _MAX and convert_in_text(text, False)[1] > 0


def is_moment(text: str) -> bool:
    if len(text) > 100:
        return False
    from forge.tools.devtools.datetimes import parse_moment

    try:
        parse_moment(text)
    except ValueError:
        return False
    return bool(text.strip())


def is_cron(text: str) -> bool:
    candidate = text.strip()
    if not candidate or len(candidate) > 200 or "\n" in candidate:
        return False
    from forge.tools.devtools.cron import CronError, is_reboot, parse, split_line

    schedule, _command = split_line(candidate)
    if is_reboot(schedule):
        return True
    if not schedule.startswith("@") and not all(_CRON_FIELD.match(f) for f in schedule.split()):
        return False
    try:
        parse(schedule)
    except CronError:
        return False
    return True

"""Date and time helpers for the developer tools (no Qt)."""

from __future__ import annotations

import email.utils
from collections.abc import Callable
from datetime import UTC, datetime

from forge.core.timestamps import epoch_to_iso

Text = Callable[..., str]  # tr()


def now_iso_local(now: datetime | None = None) -> str:
    """For example 2026-10-13T14:05:09+02:00."""
    moment = (now or datetime.now(UTC)).astimezone()
    return moment.isoformat(timespec="seconds")


def now_iso_utc(now: datetime | None = None) -> str:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def now_epoch(now: datetime | None = None) -> str:
    return str(int((now or datetime.now(UTC)).timestamp()))


def today(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone().date().isoformat()


def parse_moment(text: str, now: datetime | None = None) -> datetime:
    """A moment from a Unix timestamp (s, ms, us or ns), an ISO 8601 date-time,
    an RFC 2822 date (e-mail, HTTP) or "now". Naive dates are read as UTC."""
    value = text.strip()
    if not value or value.lower() == "now":
        return (now or datetime.now(UTC)).astimezone(UTC)
    iso = epoch_to_iso(value)
    if iso is not None:
        return datetime.fromisoformat(iso)
    try:
        moment = datetime.fromisoformat(value.replace(" ", "T", 1))
    except ValueError:
        try:
            moment = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError("not a timestamp or a date") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


def relative(moment: datetime, tr: Text, now: datetime | None = None) -> str:
    """ "in 1 h 8 min", "3 d 2 h ago": two units at most, rounded down."""
    seconds = int((moment - (now or datetime.now(UTC))).total_seconds())
    size = abs(seconds)
    days, rest = divmod(size, 86_400)
    hours, rest = divmod(rest, 3_600)
    minutes = rest // 60
    if days:
        parts = [tr("{count} d", count=days)] + ([tr("{count} h", count=hours)] if hours else [])
    elif hours:
        parts = [tr("{count} h", count=hours)]
        if minutes:
            parts.append(tr("{count} min", count=minutes))
    elif minutes:
        parts = [tr("{count} min", count=minutes)]
    else:
        return tr("now")
    span = " ".join(parts)
    return tr("in {span}", span=span) if seconds > 0 else tr("{span} ago", span=span)


def conversions(moment: datetime, tr: Text, now: datetime | None = None) -> list[tuple[str, str]]:
    """Rows of (label, value) for the date and time converter."""
    utc = moment.astimezone(UTC)
    local = moment.astimezone()
    micros = int(utc.timestamp() * 1_000_000)
    spec = "milliseconds" if micros % 1_000_000 else "seconds"
    return [
        (tr("Unix seconds"), str(micros // 1_000_000)),
        (tr("Unix milliseconds"), str(micros // 1_000)),
        (tr("ISO 8601 (UTC)"), utc.isoformat(timespec=spec).replace("+00:00", "Z")),
        (tr("ISO 8601 (local)"), local.isoformat(timespec=spec)),
        (tr("RFC 2822"), email.utils.format_datetime(utc)),
        (tr("Relative"), relative(moment, tr, now)),
    ]

"""Cron expressions (no Qt): parse them, explain them and list the next run times.

Five fields (minute hour day-of-month month day-of-week), or six with seconds
first, as in Quartz and Spring. Supported: ``*``, numbers, ranges ``1-5``,
steps ``*/15`` and ``10-50/10``, lists ``1,15``, month and weekday names
(``JAN``, ``MON``), Sunday as 0 or 7, and the shortcuts ``@yearly``,
``@annually``, ``@monthly``, ``@weekly``, ``@daily``, ``@midnight`` and
``@hourly``. ``@reboot`` (at startup) is recognised but has no schedule. As in
Vixie cron, a job with both a day of the month and a day of the week
restricted runs when either one matches.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

Text = Callable[..., str]  # tr()

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}
REBOOT = "@reboot"

# Field kinds, in the order of a six-field expression.
SECOND, MINUTE, HOUR, DAY, MONTH, WEEKDAY = "second", "minute", "hour", "day", "month", "weekday"
_RANGES = {
    SECOND: (0, 59),
    MINUTE: (0, 59),
    HOUR: (0, 23),
    DAY: (1, 31),
    MONTH: (1, 12),
    WEEKDAY: (0, 7),
}
_NAMES = {MONTH: _MONTHS, WEEKDAY: _DAYS}
_FIELD_NAMES = {
    SECOND: "second",
    MINUTE: "minute",
    HOUR: "hour",
    DAY: "day of month",
    MONTH: "month",
    WEEKDAY: "day of week",
}


class CronError(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    values: frozenset[int]
    wildcard: bool  # "*" (possibly with a step): not a restriction for day matching
    step: int | None  # for "*/n"

    @property
    def any(self) -> bool:
        """Plain ``*``: every value."""
        return self.wildcard and self.step is None

    @property
    def single(self) -> int | None:
        return next(iter(self.values)) if len(self.values) == 1 and not self.wildcard else None

    def span(self) -> tuple[int, int] | None:
        """(first, last) when the values are one unbroken range of three or more."""
        ranges = _ranges(self.values)
        if self.wildcard or len(ranges) != 1 or ranges[0][1] - ranges[0][0] < 2:
            return None
        return ranges[0]


@dataclass(frozen=True)
class Cron:
    minute: Field
    hour: Field
    day: Field
    month: Field
    weekday: Field
    second: Field | None = None  # six-field expressions only

    def matches(self, moment: datetime) -> bool:
        if self.second is not None and moment.second not in self.second.values:
            return False
        if moment.minute not in self.minute.values or moment.hour not in self.hour.values:
            return False
        if moment.month not in self.month.values:
            return False
        return self._day_matches(moment)

    def _day_matches(self, moment: datetime) -> bool:
        day_ok = moment.day in self.day.values
        weekday_ok = (moment.isoweekday() % 7) in self.weekday.values
        if self.day.wildcard or self.weekday.wildcard:
            return day_ok and weekday_ok
        return day_ok or weekday_ok

    def next_runs(self, after: datetime, count: int = 10) -> list[datetime]:
        """The next ``count`` moments after ``after`` (same time zone, naive or aware)."""
        runs: list[datetime] = []
        moment = after.replace(second=0, microsecond=0)
        if self.second is None:
            moment += timedelta(minutes=1)
        limit = moment + timedelta(days=366 * 5)
        while len(runs) < count and moment < limit:
            if moment.month not in self.month.values:
                year = moment.year + (moment.month == 12)
                moment = moment.replace(
                    year=year, month=moment.month % 12 + 1, day=1, hour=0, minute=0
                )
                continue
            if not self._day_matches(moment):
                moment = (moment + timedelta(days=1)).replace(hour=0, minute=0)
                continue
            if moment.hour not in self.hour.values:
                moment = (moment + timedelta(hours=1)).replace(minute=0)
                continue
            if moment.minute not in self.minute.values:
                moment += timedelta(minutes=1)
                continue
            if self.second is None:
                runs.append(moment)
            else:
                for second in sorted(self.second.values):
                    run = moment.replace(second=second)
                    if run > after and len(runs) < count:
                        runs.append(run)
            moment += timedelta(minutes=1)
        return runs


def _number(token: str, names: tuple[str, ...], low: int, high: int, field: str) -> int:
    token = token.strip().lower()
    if names and token[:3] in names and token.isalpha():
        return names.index(token[:3]) + (1 if names is _MONTHS else 0)
    if not token.isdigit():
        raise CronError(f"'{token}' is not a valid value for {field}")
    value = int(token)
    if not low <= value <= high:
        raise CronError(f"{value} is out of range for {field} ({low}-{high})")
    return value


def _field(text: str, kind: str) -> Field:
    low, high = _RANGES[kind]
    names = _NAMES.get(kind, ())
    field = _FIELD_NAMES[kind]
    values: set[int] = set()
    wildcard = False
    star_step: int | None = None
    for part in text.split(","):
        if not part:
            raise CronError(f"empty value in {field}")
        base, _, step_text = part.partition("/")
        step = 1
        if step_text:
            if not step_text.isdigit() or int(step_text) == 0:
                raise CronError(f"'{step_text}' is not a valid step in {field}")
            step = int(step_text)
        if base in ("*", "?"):  # "?" is Quartz for "no specific value"
            start, end = low, high
            wildcard = True
            star_step = step if step_text else None
        elif "-" in base:
            first, _, last = base.partition("-")
            start = _number(first, names, low, high, field)
            end = _number(last, names, low, high, field)
            if start > end:
                raise CronError(f"range {base} in {field} runs backwards")
        else:
            start = _number(base, names, low, high, field)
            end = high if step_text else start
        values.update(range(start, end + 1, step))
    result = Field(frozenset(values), wildcard, star_step)
    if kind == WEEKDAY and 7 in result.values:  # Sunday as 7
        result = Field(frozenset((result.values - {7}) | {0}), result.wildcard, result.step)
    return result


def parse_field(text: str, kind: str) -> Field:
    """One field on its own, to point at the field that is wrong."""
    return _field(text, kind)


def split(expression: str) -> list[tuple[str, str]]:
    """The fields as (kind, text), after expanding a shortcut such as ``@daily``."""
    text = expression.strip()
    text = SHORTCUTS.get(text.lower(), text)
    parts = text.split()
    if len(parts) == 5:
        kinds = [MINUTE, HOUR, DAY, MONTH, WEEKDAY]
    elif len(parts) == 6:
        kinds = [SECOND, MINUTE, HOUR, DAY, MONTH, WEEKDAY]
    else:
        raise CronError(
            "a cron expression has five fields (minute hour day-of-month month day-of-week), "
            "or six with seconds first"
        )
    return list(zip(kinds, parts, strict=True))


def is_reboot(expression: str) -> bool:
    return expression.strip().lower() == REBOOT


def split_line(line: str) -> tuple[str, str]:
    """A crontab line as (schedule, command), e.g. ``0 9 * * 1-5 backup.sh``.

    Six fields followed by nothing are read as a schedule with seconds; with
    more words after the fifth field, the rest is the command.
    """
    words = line.strip().split()
    if not words:
        return "", ""
    if words[0].startswith("@"):
        return words[0], " ".join(words[1:])
    if len(words) == 6:
        try:
            parse(" ".join(words))
            return " ".join(words), ""
        except CronError:
            pass
    return " ".join(words[:5]), " ".join(words[5:])


def parse(expression: str) -> Cron:
    if is_reboot(expression):
        raise CronError("@reboot runs at startup and has no schedule")
    fields = {kind: _field(text, kind) for kind, text in split(expression)}
    return Cron(
        minute=fields[MINUTE],
        hour=fields[HOUR],
        day=fields[DAY],
        month=fields[MONTH],
        weekday=fields[WEEKDAY],
        second=fields.get(SECOND),
    )


# Explanation -------------------------------------------------------------------------


def _ranges(values: frozenset[int]) -> list[tuple[int, int]]:
    ordered = sorted(values)
    result: list[tuple[int, int]] = []
    for value in ordered:
        if result and value == result[-1][1] + 1:
            result[-1] = (result[-1][0], value)
        else:
            result.append((value, value))
    return result


def _join(values: frozenset[int], name: Callable[[int], str], tr: Text) -> str:
    parts = []
    for start, end in _ranges(values):
        if end - start >= 2:
            parts.append(tr("{first} to {last}", first=name(start), last=name(end)))
        else:
            parts.extend(name(v) for v in range(start, end + 1))
    if len(parts) == 1:
        return parts[0]
    return tr("{items} and {last}", items=", ".join(parts[:-1]), last=parts[-1])


def clock(hour: int, minute: int, clock24: bool = True, second: int | None = None) -> str:
    """09:05, or 9:05 AM with ``clock24`` off; with ``second`` 09:05:30."""
    tail = f":{second:02d}" if second is not None else ""
    if clock24:
        return f"{hour:02d}:{minute:02d}{tail}"
    return f"{hour % 12 or 12}:{minute:02d}{tail} {'AM' if hour < 12 else 'PM'}"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _seconds_phrase(second: Field | None, tr: Text) -> str | None:
    if second is None or second.values == frozenset({0}):
        return None
    if second.any:
        return tr("Every second")
    if second.wildcard and second.step:
        return tr("Every {count} seconds", count=second.step)
    return tr("At second {seconds}", seconds=_join(second.values, str, tr))


def _time_phrase(minute: Field, hour: Field, tr: Text, clock24: bool) -> str:
    """When in the day: "At 09:00", "Every 15 minutes, between 09:00 and 17:59"."""
    m_single = minute.single
    if minute.any and hour.any:
        return tr("Every minute")
    if minute.wildcard and minute.step and hour.any:
        return tr("Every {count} minutes", count=minute.step)
    if m_single == 0 and hour.any:
        return tr("Every hour, on the hour")
    if m_single is not None and hour.any:
        return tr("At minute {minute} past every hour", minute=m_single)
    if m_single is not None and hour.wildcard and hour.step:
        return tr("At minute {minute} past every {count} hours", minute=m_single, count=hour.step)
    span = hour.span()
    if m_single is not None and span is not None:
        return tr(
            "Every hour from {first} to {last}",
            first=clock(span[0], m_single, clock24),
            last=clock(span[1], m_single, clock24),
        )
    if not minute.wildcard and not hour.wildcard and len(minute.values) * len(hour.values) <= 8:
        times = [clock(h, m, clock24) for h in sorted(hour.values) for m in sorted(minute.values)]
        if len(times) == 1:
            return tr("At {time}", time=times[0])
        return tr("At {times} and {last}", times=", ".join(times[:-1]), last=times[-1])

    h_single = hour.single
    m_span = minute.span()
    if h_single is not None and m_span is not None:
        return tr(
            "Every minute from {first} to {last}",
            first=clock(h_single, m_span[0], clock24),
            last=clock(h_single, m_span[1], clock24),
        )
    if minute.any:
        when = tr("Every minute")
    elif minute.wildcard and minute.step:
        when = tr("Every {count} minutes", count=minute.step)
    elif len(minute.values) == 1:
        when = tr("At minute {minutes}", minutes=_join(minute.values, str, tr))
    else:
        when = tr("At minutes {minutes}", minutes=_join(minute.values, str, tr))
    if h_single is not None:
        span = (h_single, h_single)
    if hour.any:
        return tr("{minutes} past every hour", minutes=when) if not minute.wildcard else when
    if hour.wildcard and hour.step:
        return tr("{minutes}, every {count} hours", minutes=when, count=hour.step)
    if span is not None:
        return tr(
            "{minutes}, between {first} and {last}",
            minutes=when,
            first=clock(span[0], 0, clock24),
            last=clock(span[1], 59, clock24),
        )
    hours = _join(hour.values, str, tr)
    return tr("{minutes}, during the hours {hours}", minutes=when, hours=hours)


def describe(
    cron: Cron,
    tr: Text,
    day_names: list[str],
    month_names: list[str],
    clock24: bool = True,
) -> str:
    """One sentence, e.g. "At 09:00, Monday to Friday"."""
    when = _time_phrase(cron.minute, cron.hour, tr, clock24)
    seconds = _seconds_phrase(cron.second, tr)
    minute, hour = cron.minute.single, cron.hour.single
    second = cron.second.single if cron.second is not None else None
    if seconds is not None and second is not None and minute is not None and hour is not None:
        when = tr("At {time}", time=clock(hour, minute, clock24, second))
    elif seconds is not None:
        every_minute = tr("Every minute")
        if cron.minute.any and when.startswith(every_minute):
            # "Every 5 seconds, between 09:00 and 09:59", not "..., every minute, ...".
            rest = when[len(every_minute) :].lstrip(", ")
            when = f"{seconds}, {rest}" if rest else seconds
        else:
            when = f"{seconds}, {_lower_first(when)}"

    parts = [when]
    if cron.day.wildcard and cron.day.step:
        parts.append(tr("every {count} days", count=cron.day.step))
    elif not cron.day.wildcard:
        parts.append(tr("on day {days} of the month", days=_join(cron.day.values, str, tr)))
    if not cron.weekday.wildcard:
        names = _weekdays(cron.weekday.values, tr, day_names)
        if not cron.day.wildcard:
            parts.append(tr("or on {days}", days=names))
        else:
            parts.append(names)
    if not cron.month.wildcard:
        parts.append(
            tr("in {months}", months=_join(cron.month.values, lambda m: month_names[m - 1], tr))
        )
    elif cron.month.step:
        parts.append(tr("every {count} months", count=cron.month.step))
    return ", ".join(parts)


def _weekdays(values: frozenset[int], tr: Text, day_names: list[str]) -> str:
    # Monday first, as people read a week.
    ordered = frozenset((d - 1) % 7 for d in values)
    return _join(ordered, lambda d: day_names[(d + 1) % 7], tr)


def field_meaning(
    kind: str, field: Field, tr: Text, day_names: list[str], month_names: list[str]
) -> str:
    """A few words for one field, e.g. "Monday to Friday" or "every 15"."""
    if field.any:
        return {
            SECOND: tr("every second"),
            MINUTE: tr("every minute"),
            HOUR: tr("every hour"),
            DAY: tr("every day"),
            MONTH: tr("every month"),
            WEEKDAY: tr("any day"),
        }[kind]
    if field.wildcard and field.step:
        return tr("every {count}", count=field.step)
    if kind == WEEKDAY:
        return _weekdays(field.values, tr, day_names)
    if kind == MONTH:
        return _join(field.values, lambda m: month_names[m - 1], tr)
    return _join(field.values, str, tr)

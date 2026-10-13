"""Cron expressions (no Qt): parse the five standard fields, explain them and
list the next run times.

Supported: ``*``, numbers, ranges ``1-5``, steps ``*/15`` and ``10-50/10``,
lists ``1,15``, month and weekday names (``JAN``, ``MON``), Sunday as 0 or 7,
and the shortcuts ``@yearly``, ``@monthly``, ``@weekly``, ``@daily`` and
``@hourly``. As in Vixie cron, a job with both a day of the month and a day of
the week restricted runs when either one matches.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

Text = Callable[..., str]  # tr()

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")
_SHORTCUTS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
}


class CronError(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    values: frozenset[int]
    wildcard: bool  # "*" (possibly with a step): not a restriction for day matching
    step: int | None  # for "*/n"


@dataclass(frozen=True)
class Cron:
    minute: Field
    hour: Field
    day: Field
    month: Field
    weekday: Field

    def matches(self, moment: datetime) -> bool:
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
        moment = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
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
            runs.append(moment)
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


def _field(text: str, low: int, high: int, field: str, names: tuple[str, ...] = ()) -> Field:
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
        if base == "*":
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
    return Field(frozenset(values), wildcard, star_step)


def parse(expression: str) -> Cron:
    text = expression.strip()
    if text.lower() == "@reboot":
        raise CronError("@reboot runs at startup and has no schedule")
    text = _SHORTCUTS.get(text.lower(), text)
    parts = text.split()
    if len(parts) != 5:
        raise CronError(
            "a cron expression has five fields: minute hour day-of-month month day-of-week"
        )
    weekday = _field(parts[4], 0, 7, "day of week", _DAYS)
    if 7 in weekday.values:  # Sunday as 7
        weekday = Field(frozenset((weekday.values - {7}) | {0}), weekday.wildcard, weekday.step)
    return Cron(
        minute=_field(parts[0], 0, 59, "minute"),
        hour=_field(parts[1], 0, 23, "hour"),
        day=_field(parts[2], 1, 31, "day of month"),
        month=_field(parts[3], 1, 12, "month", _MONTHS),
        weekday=weekday,
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


def describe(cron: Cron, tr: Text, day_names: list[str], month_names: list[str]) -> str:
    """One sentence, e.g. "At 09:00, Monday to Friday"."""
    minute, hour = cron.minute, cron.hour
    if minute.wildcard and minute.step is None and hour.wildcard and hour.step is None:
        when = tr("Every minute")
    elif minute.wildcard and minute.step and hour.wildcard and hour.step is None:
        when = tr("Every {count} minutes", count=minute.step)
    elif len(minute.values) == 1 and hour.wildcard and hour.step is None:
        when = tr("Every hour at minute {minute}", minute=min(minute.values))
    elif len(minute.values) == 1 and hour.wildcard and hour.step:
        when = tr(
            "Every {count} hours at minute {minute}", count=hour.step, minute=min(minute.values)
        )
    elif len(minute.values) == 1 and len(hour.values) <= 6:
        times = ", ".join(f"{h:02d}:{min(minute.values):02d}" for h in sorted(hour.values))
        when = tr("At {times}", times=times)
    else:
        when = tr(
            "At minute {minutes} past hour {hours}",
            minutes=_join(minute.values, str, tr),
            hours=_join(hour.values, str, tr),
        )

    parts = [when]
    if not cron.day.wildcard:
        parts.append(tr("on day {days} of the month", days=_join(cron.day.values, str, tr)))
    if not cron.weekday.wildcard:
        # Monday first, as people read a week.
        ordered = frozenset((d - 1) % 7 for d in cron.weekday.values)
        names = _join(ordered, lambda d: day_names[(d + 1) % 7], tr)
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

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from forge.tools.devtools import cron, datetimes, transforms, uuids


def tr(text: str, **values: object) -> str:
    return text.format(**values)


DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]  # fmt: skip


def test_hashes_match_known_values(tmp_path: Path) -> None:
    assert transforms.hash_text("abc", "md5") == "900150983cd24fb0d6963f7d28e17f72"
    assert transforms.hash_text("abc", "sha256").startswith("ba7816bf8f01cfea")
    file = tmp_path / "a.bin"
    file.write_bytes(b"abc")
    assert transforms.hash_file(file)["sha1"] == "a9993e364706816aba3e25717850c26c9cd0d89d"


@pytest.mark.parametrize(
    ("encode", "decode", "plain"),
    [
        (transforms.base64_encode, transforms.base64_decode, "héllo wörld"),
        (transforms.url_encode, transforms.url_decode, "a b&c=d/é"),
        (transforms.html_escape, transforms.html_unescape, '<a href="x">&</a>'),
        (transforms.json_escape, transforms.json_unescape, 'line\n"quoted"\ttab'),
    ],
)
def test_encodings_round_trip(encode, decode, plain: str) -> None:  # type: ignore[no-untyped-def]
    assert decode(encode(plain)) == plain


def test_decoding_errors_are_readable() -> None:
    with pytest.raises(ValueError, match="Base64"):
        transforms.base64_decode("not base64!")
    with pytest.raises(ValueError, match="UTF-8"):
        transforms.base64_decode("//79")  # bytes ff fe fd
    assert transforms.base64_decode("aGk") == "hi"  # missing padding is fine


def test_jwt() -> None:
    token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    decoded = transforms.decode_jwt(token)
    assert decoded["header"] == {"alg": "HS256", "typ": "JWT"}
    assert decoded["payload"]["name"] == "John Doe"  # type: ignore[index]
    with pytest.raises(ValueError):
        transforms.decode_jwt("a.b")


def test_letter_case() -> None:
    assert transforms.camel_case("Hello big World") == "helloBigWorld"
    assert transforms.pascal_case("user_id value") == "UserIdValue"
    assert transforms.snake_case("parseHTTPResponse") == "parse_http_response"
    assert transforms.kebab_case("Some Title 2") == "some-title-2"
    assert transforms.title_case("hello wORLD") == "Hello World"
    assert transforms.snake_case("firstName\nlastName") == "first_name\nlast_name"


def test_lines() -> None:
    assert transforms.sort_lines(["file10", "File2", "file1"]) == ["file1", "File2", "file10"]
    assert transforms.sort_lines(["a", "b"], descending=True) == ["b", "a"]
    assert transforms.unique_lines(["a", "b", "a"]) == ["a", "b"]
    assert transforms.trim_trailing(["a  ", "b\t"]) == ["a", "b"]


def test_uuids() -> None:
    one = uuids.generate(uuids.UuidOptions())
    assert len(one) == 36 and one[14] == "4"
    many = uuids.generate(uuids.UuidOptions(count=5, version=7, uppercase=True, braces=True))
    lines = many.split("\n")
    assert len(lines) == 5 and all(line.startswith("{") and line[15] == "7" for line in lines)
    compact = uuids.generate(uuids.UuidOptions(hyphens=False, separator=", ", count=2))
    assert len(compact.split(", ")[0]) == 32
    first, second = uuids.uuid7(1_000), uuids.uuid7(2_000)
    assert first < second  # time ordered
    assert first.variant == "specified in RFC 4122"


def test_cron_next_runs_and_explanation() -> None:
    weekdays = cron.parse("0 9 * * MON-FRI")
    start = datetime(2026, 10, 9, 10, 0)  # a Friday after 09:00
    runs = weekdays.next_runs(start, 3)
    assert [r.strftime("%a %H:%M") for r in runs] == ["Mon 09:00", "Tue 09:00", "Wed 09:00"]
    assert cron.describe(weekdays, tr, DAYS, MONTHS) == "At 09:00, Monday to Friday"
    every = cron.parse("*/15 * * * *")
    assert cron.describe(every, tr, DAYS, MONTHS) == "Every 15 minutes"
    assert every.next_runs(datetime(2026, 1, 1, 0, 7), 2)[0].minute == 15
    yearly = cron.parse("@yearly")
    assert yearly.next_runs(datetime(2026, 3, 1), 1)[0] == datetime(2027, 1, 1)
    sunday = cron.parse("30 6 * * 7")
    assert sunday.next_runs(datetime(2026, 10, 13), 1)[0].isoweekday() == 7
    either = cron.parse("0 0 13 * FRI")  # the 13th OR any Friday
    assert len(either.next_runs(datetime(2026, 10, 1), 6)) == 6
    text = cron.describe(cron.parse("0 0 1 JAN,JUL *"), tr, DAYS, MONTHS)
    assert text == "At 00:00, on day 1 of the month, in January and July"


@pytest.mark.parametrize(
    ("expression", "text"),
    [
        ("*/15 9-17 * * MON-FRI", "Every 15 minutes, between 09:00 and 17:59, Monday to Friday"),
        ("0 9-17 * * *", "Every hour from 09:00 to 17:00"),
        ("30 */2 * * *", "At minute 30 past every 2 hours"),
        ("0,30 9,17 * * *", "At 09:00, 09:30, 17:00 and 17:30"),
        ("@hourly", "Every hour, on the hour"),
        ("1,10 * * * *", "At minutes 1 and 10 past every hour"),
        ("0-10 8 * * *", "Every minute from 08:00 to 08:10"),
        ("0 12 */2 * *", "At 12:00, every 2 days"),
        ("*/10 * * * * *", "Every 10 seconds"),
        ("30 0 9 * * *", "At 09:00:30"),
        ("*/5 * 9 * * *", "Every 5 seconds, between 09:00 and 09:59"),
    ],
)
def test_cron_descriptions(expression: str, text: str) -> None:
    assert cron.describe(cron.parse(expression), tr, DAYS, MONTHS) == text


def test_cron_twelve_hour_clock_and_fields() -> None:
    parsed = cron.parse("0 22 * * 1-5")
    assert cron.describe(parsed, tr, DAYS, MONTHS, clock24=False) == "At 10:00 PM, Monday to Friday"
    assert cron.field_meaning(cron.WEEKDAY, parsed.weekday, tr, DAYS, MONTHS) == (
        "Monday to Friday"
    )
    assert cron.field_meaning(cron.DAY, parsed.day, tr, DAYS, MONTHS) == "every day"
    every = cron.parse_field("*/15", cron.MINUTE)
    assert cron.field_meaning(cron.MINUTE, every, tr, DAYS, MONTHS) == "every 15"


def test_cron_seconds_and_crontab_lines() -> None:
    runs = cron.parse("*/20 * * * * *").next_runs(datetime(2026, 1, 1, 0, 0, 30), 3)
    assert [r.strftime("%H:%M:%S") for r in runs] == ["00:00:40", "00:01:00", "00:01:20"]
    assert cron.split_line("0 9 * * 1-5 /opt/backup.sh --all") == (
        "0 9 * * 1-5",
        "/opt/backup.sh --all",
    )
    assert cron.split_line("0 0 9 * * MON") == ("0 0 9 * * MON", "")
    assert cron.split_line("@daily run.sh") == ("@daily", "run.sh")
    assert cron.is_reboot(" @REBOOT ")


def test_relative_times() -> None:
    now = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
    later = datetime(2026, 10, 27, 13, 8, tzinfo=UTC)
    assert datetimes.relative(later, tr, now) == "in 1 h 8 min"
    assert datetimes.relative(datetime(2026, 10, 24, 10, 0, tzinfo=UTC), tr, now) == "3 d 2 h ago"
    assert datetimes.relative(now, tr, now) == "now"


@pytest.mark.parametrize("bad", ["* * * *", "60 * * * *", "5-1 * * * *", "*/0 * * * *", "@reboot"])
def test_cron_errors(bad: str) -> None:
    with pytest.raises(cron.CronError):
        cron.parse(bad)


def test_date_conversions() -> None:
    now = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    moment = datetimes.parse_moment("1700000000123")
    rows = dict(datetimes.conversions(moment, tr, now))
    assert rows["Unix seconds"] == "1700000000"
    assert rows["ISO 8601 (UTC)"] == "2023-11-14T22:13:20.123Z"
    assert rows["Relative"].endswith("ago")
    assert datetimes.parse_moment("Tue, 14 Nov 2023 22:13:20 +0000").timestamp() == 1700000000
    assert datetimes.parse_moment("2023-11-14 22:13:20").timestamp() == 1700000000
    assert datetimes.now_iso_utc(now) == "2026-10-13T12:00:00Z"
    assert datetimes.now_epoch(now) == "1791892800"
    with pytest.raises(ValueError):
        datetimes.parse_moment("yesterday-ish")

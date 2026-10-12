from __future__ import annotations

import pytest

from forge.core.csvtext import column_at, find_problem, join_records, split_records
from forge.tools.csv_tool import ops

TEXT = 'name;age;city\r\nBob;42;"Nij;megen"\r\nann;7;Wijchen\r\nBob;42;"Nij;megen"\r\n'


def records(text: str = TEXT, delimiter: str = ";") -> list:
    return split_records(text, delimiter)


@pytest.mark.parametrize(
    "text",
    [TEXT, "a,b\n1,2", 'a,"multi\nline",c\n', "\n\nx\n", "", "a\r\nb\rc\n"],
)
def test_records_round_trip_exactly(text: str) -> None:
    assert join_records(split_records(text, ","), ",") == text


def test_column_at_caret_and_problems() -> None:
    assert column_at('a,"b,c",d', ",") == 2
    assert column_at("a,b\nc", ",") == 0
    problem = find_problem("a,b\n1,2,3\n", ",")
    assert problem is not None and (problem.line, problem.expected, problem.found) == (2, 2, 3)
    assert find_problem('a,b\n1,"open\n', ",") is not None
    assert find_problem("a,b\n\n1,2\n", ",") is None  # blank lines are fine


def test_align_and_shrink() -> None:
    aligned = join_records(ops.align(records("id,name\n1,Ann\n100,Bo\n", ",")), ",")
    assert aligned == "id ,name\n1  ,Ann\n100,Bo\n"
    assert join_records(ops.shrink(records(aligned, ",")), ",") == "id,name\n1,Ann\n100,Bo\n"


def test_sort_keeps_header_numbers_and_line_endings() -> None:
    text = "n,v\n10,a\n9,b\nx,c"
    result = join_records(ops.sort_rows(records(text, ","), 0, False, True), ",")
    assert result == "n,v\n9,b\n10,a\nx,c"
    result = join_records(ops.sort_rows(records(text, ","), 1, True, True), ",")
    assert result == "n,v\nx,c\n9,b\n10,a"


def test_remove_duplicates() -> None:
    kept, removed = ops.remove_duplicates(records(), True)
    assert removed == 1
    assert join_records(kept, ";") == 'name;age;city\r\nBob;42;"Nij;megen"\r\nann;7;Wijchen\r\n'


def test_change_delimiter_quotes_when_needed() -> None:
    result = join_records(ops.change_delimiter(records(), ","), ",")
    assert result.splitlines()[1] == 'Bob,42,"Nij;megen"'
    text = join_records(ops.change_delimiter(records("a;b,c\n", ";"), ","), ",")
    assert text == 'a,"b,c"\n'


def test_header_detection() -> None:
    assert ops.has_header(records(), ";")
    assert not ops.has_header(records("1,2\n3,4\n5,6\n", ","), ",")


@pytest.mark.parametrize(
    ("value", "iso"),
    [
        ("1700000000", "2023-11-14T22:13:20Z"),
        ("1700000000123", "2023-11-14T22:13:20.123Z"),
        ("1700000000123456", "2023-11-14T22:13:20.123456Z"),
        ("1700000000123456789", "2023-11-14T22:13:20.123456Z"),
        ("1700000000.5", "2023-11-14T22:13:20.500Z"),
        ("0", None),
        ("hello", None),
        ("12345678901", None),
    ],
)
def test_epoch_to_iso(value: str, iso: str | None) -> None:
    assert ops.epoch_to_iso(value) == iso


def test_iso_to_epoch() -> None:
    assert ops.iso_to_epoch("2023-11-14T22:13:20Z") == "1700000000"
    assert ops.iso_to_epoch("2023-11-14 23:13:20+01:00") == "1700000000"
    assert ops.iso_to_epoch("2023-11-14T22:13:20.123Z", milliseconds=True) == "1700000000123"
    assert ops.iso_to_epoch("2023-11-14T22:13:20.5") == "1700000000.5"
    assert ops.iso_to_epoch("not a date") is None


def test_convert_column_and_text() -> None:
    text = "id,ts\n1,1700000000\n2,\n3,soon\n"
    converted, count = ops.convert_column(records(text, ","), 1, ops.epoch_to_iso, True, ",")
    assert count == 1
    assert join_records(converted, ",") == "id,ts\n1,2023-11-14T22:13:20Z\n2,\n3,soon\n"
    result, count = ops.convert_in_text("at 1700000000 and 1700000000000 id 12", True)
    assert count == 2 and "12" in result and "2023-11-14T22:13:20Z" in result
    back, count = ops.convert_in_text(result, False)
    assert count == 2 and back.startswith("at 1700000000 and 1700000000 ")


def test_exports() -> None:
    data = records('id,name,ok\n1,"A, B",true\n007,x,\n', ",")
    json_text = ops.to_json(data, True, "  ")
    assert '"id": 1' in json_text and '"name": "A, B"' in json_text
    assert '"id": "007"' in json_text and '"ok": true' in json_text
    table = ops.to_markdown(records("a,b\n1,x|y\n", ","), True)
    assert table == "| a | b |\n| --- | --- |\n| 1 | x\\|y |\n"


def test_sort_understands_decimal_commas() -> None:
    text = "v\n10\n3,5\n4\n"
    result = join_records(ops.sort_rows(records(text, ";"), 0, False, True), ";")
    assert result == "v\n3,5\n4\n10\n"

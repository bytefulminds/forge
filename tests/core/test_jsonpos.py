from __future__ import annotations

from forge.core.jsonpos import find_offset, line_and_column

TEXT = """{
    "name": "forge",
    "tags": ["a", {"deep": [1, 2]}],
    "esc\\"aped": null,
    "empty": {}
}"""


def where(path: tuple[str | int, ...]) -> tuple[int, int] | None:
    offset = find_offset(TEXT, path)
    return None if offset is None else line_and_column(TEXT, offset)


def test_paths_point_at_keys_and_array_items() -> None:
    assert where(()) == (0, 0)
    assert where(("name",)) == (1, 4)
    assert where(("tags",)) == (2, 4)
    assert where(("tags", 0)) == (2, 13)
    assert where(("tags", 1, "deep")) == (2, 19)
    assert where(("tags", 1, "deep", 1)) == (2, 31)
    assert where(('esc"aped',)) == (3, 4)
    assert where(("empty",)) == (4, 4)


def test_missing_paths_and_broken_text() -> None:
    assert where(("nope",)) is None
    assert where(("tags", 5)) is None
    assert find_offset('{"a": [1, 2', ("a", 1)) == 10
    assert find_offset('{"a": [1, 2', ("b",)) is None

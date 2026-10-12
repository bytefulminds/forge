from __future__ import annotations

from forge.tools.compare.diff import ADDED, CHANGED, EQUAL, FILLER, REMOVED, compare


def test_aligned_rows_and_counts() -> None:
    left = "one\ntwo\nthree\nfour\n"
    right = "one\nTWO\nthree\nfour\nfive\n"
    result = compare(left, right)
    assert len(result.left) == len(result.right)
    assert [r.kind for r in result.left] == [EQUAL, CHANGED, EQUAL, EQUAL, FILLER]
    assert [r.kind for r in result.right] == [EQUAL, CHANGED, EQUAL, EQUAL, ADDED]
    assert result.right[4].number == 5 and result.left[4].number is None
    assert (result.changed, result.added, result.removed) == (1, 1, 0)
    assert result.blocks == [1, 4]


def test_inline_ranges_for_changed_lines() -> None:
    result = compare("value = 10\n", "value = 12\n")
    assert result.left[0].inline == [(9, 10)]
    assert result.right[0].inline == [(9, 10)]


def test_removed_and_identical() -> None:
    result = compare("a\nb\n", "a\n")
    assert [r.kind for r in result.left] == [EQUAL, REMOVED]
    assert compare("x\n", "x\n").identical

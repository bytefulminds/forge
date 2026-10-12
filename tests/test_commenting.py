from __future__ import annotations

from forge.editor.commenting import CommentMode, CommentStyle, apply_comment

HASH = CommentStyle("#")
XML = CommentStyle("", "<!--", "-->")


def test_toggle_comments_at_smallest_indent() -> None:
    lines = ["    a = 1", "", "        b = 2"]
    assert apply_comment(lines, HASH, CommentMode.TOGGLE) == ["    # a = 1", "", "    #     b = 2"]


def test_toggle_uncomments_when_all_commented() -> None:
    lines = ["    # a = 1", "#b"]
    assert apply_comment(lines, HASH, CommentMode.TOGGLE) == ["    a = 1", "b"]


def test_toggle_comments_mixed_selection() -> None:
    lines = ["# a", "b"]
    assert apply_comment(lines, HASH, CommentMode.TOGGLE) == ["# # a", "# b"]


def test_uncomment_leaves_plain_lines() -> None:
    assert apply_comment(["# a", "b"], HASH, CommentMode.UNCOMMENT) == ["a", "b"]


def test_block_style_round_trip() -> None:
    lines = ["  <a/>", "  <b/>"]
    commented = apply_comment(lines, XML, CommentMode.TOGGLE)
    assert commented == ["  <!-- <a/> -->", "  <!-- <b/> -->"]
    assert apply_comment(commented, XML, CommentMode.TOGGLE) == lines


def test_unsupported_language_is_unchanged() -> None:
    assert apply_comment(["x"], CommentStyle(), CommentMode.TOGGLE) == ["x"]

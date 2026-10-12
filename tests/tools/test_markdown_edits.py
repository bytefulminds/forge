from __future__ import annotations

from forge.tools.markdown_tool import edits


def test_toggle_wrap_round_trip() -> None:
    assert edits.toggle_wrap("x", "**") == ("**x**", 2, 1)
    assert edits.toggle_wrap("**x**", "**") == ("x", 0, 1)
    assert edits.toggle_wrap("", "`") == ("``", 1, 0)


def test_link_selects_the_part_to_type() -> None:
    assert edits.link("") == ("[text](https://)", 1, 4)
    text, start, length = edits.link("Forge")
    assert text == "[Forge](https://)" and text[start : start + length] == "https://"
    assert edits.link("https://a.nl")[0] == "[https://a.nl](https://a.nl)"


def test_heading_cycles_and_returns_to_text() -> None:
    lines = ["Title"]
    seen = []
    for _ in range(4):
        lines = edits.cycle_heading(lines)
        seen.append(lines[0])
    assert seen == ["# Title", "## Title", "### Title", "Title"]


def test_lists_toggle_and_convert() -> None:
    assert edits.toggle_bullets(["a", "", "b"]) == ["- a", "", "- b"]
    assert edits.toggle_bullets(["- a", "- b"]) == ["a", "b"]
    assert edits.toggle_numbers(["- a", "- b"]) == ["1. a", "2. b"]
    assert edits.toggle_tasks(["  - a"]) == ["  - [ ] a"]
    assert edits.toggle_bullets(["- [ ] a"]) == ["- a"]
    assert edits.toggle_bullets([""]) == ["- "]


def test_quote_and_code_block() -> None:
    assert edits.toggle_prefix(["a", "b"], "> ") == ["> a", "> b"]
    assert edits.toggle_prefix(["> a", "> b"], "> ") == ["a", "b"]
    assert edits.toggle_code_block(["x"]) == ["```", "x", "```"]
    assert edits.toggle_code_block(["```", "x", "```"]) == ["x"]


def test_table_template() -> None:
    assert edits.table(["A", "B"]).splitlines() == ["| A | B |", "| --- | --- |", "|     |     |"]


def test_wrapped_outside_tells_bold_from_italic() -> None:
    assert edits.wrapped_outside("a**", "**b", "**")
    assert not edits.wrapped_outside("a**", "**b", "*")  # bold, not italic
    assert edits.wrapped_outside(" *", "* ", "*")
    assert not edits.wrapped_outside("", "*", "*")

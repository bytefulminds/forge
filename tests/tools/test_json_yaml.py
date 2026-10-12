from __future__ import annotations

import pytest

from forge.tools.json_tool.formatter import JsonError, reformat
from forge.tools.yaml_tool.actions import check


def test_reformat_keeps_tokens_exactly() -> None:
    text = '{"b":1.50,"a":[1e10,"x\\"y",{}],"c":[]}'
    pretty = reformat(text, "  ")
    assert pretty == (
        '{\n  "b": 1.50,\n  "a": [\n    1e10,\n    "x\\"y",\n    {}\n  ],\n  "c": []\n}'
    )
    assert reformat(pretty, None) == text


def test_reformat_reports_position() -> None:
    with pytest.raises(JsonError) as info:
        reformat('{\n  "a": 1,\n  "b": }', "  ")
    assert info.value.line == 3


def test_reformat_crlf() -> None:
    assert reformat('{"a":1}', "\t", "\r\n") == '{\r\n\t"a": 1\r\n}'


def test_yaml_check() -> None:
    assert check("a: 1\n---\nb: 2\n") == (2, "", 0, 0)
    _documents, error, line, column = check("a: 1\nb: [1, 2\nc: 3\n")
    assert error and line >= 2 and column >= 1

from __future__ import annotations

import pytest

from forge.tools.xml_tool.autoclose import closing_tag
from forge.tools.xml_tool.core import XmlError, minify, pretty, xpath

DOC = '<?xml version="1.0" encoding="ISO-8859-1"?>\n<root><item id="1">café</item><item/></root>'


def test_pretty_keeps_declaration_and_text() -> None:
    result = pretty(DOC, "  ")
    assert result.startswith('<?xml version="1.0" encoding="ISO-8859-1"?>\n<root>\n')
    assert '  <item id="1">café</item>' in result


def test_minify() -> None:
    assert minify(pretty(DOC, "    ")) == DOC.replace("\n", "")


def test_error_position() -> None:
    with pytest.raises(XmlError) as info:
        pretty("<a>\n  <b>\n</a>", "  ")
    assert info.value.line == 3


def test_entities_are_not_expanded() -> None:
    bomb = '<!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'
    assert "boom" not in minify(bomb).split("]>")[-1]


def test_xpath_with_default_namespace() -> None:
    doc = '<r xmlns="urn:x">\n<i>a</i>\n<i>b</i>\n</r>'
    results = xpath(doc, "//d:i")
    assert [line for _, line in results] == [2, 3]
    assert xpath(doc, "count(//d:i)") == [("2.0", None)]


@pytest.mark.parametrize(
    ("before", "language", "expected"),
    [
        ("<item>", "xml", "</item>"),
        ('<a href="x">', "html", "</a>"),
        ("<br>", "html", None),
        ("<x/>", "xml", None),
        ("</x>", "xml", None),
        ("<?xml version='1.0'?>", "xml", None),
        ("<item>", "python", None),
    ],
)
def test_closing_tag(before: str, language: str, expected: str | None) -> None:
    assert closing_tag(before, language) == expected

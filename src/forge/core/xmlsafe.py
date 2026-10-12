"""Safe XML parsing with lxml: no entity expansion, no network access.

Shared by the XML tools and the live syntax check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from lxml import etree

_DECLARATION = re.compile(r"^\s*(<\?xml[^>]*\?>)", re.IGNORECASE)
_ENCODING = re.compile(r"""(encoding\s*=\s*)(["'])[^"']*\2""", re.IGNORECASE)


@dataclass
class XmlError(ValueError):
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return self.message


def _parser(remove_blank_text: bool) -> etree.XMLParser:
    return etree.XMLParser(
        remove_blank_text=remove_blank_text,
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
        remove_comments=False,
    )


def parse(text: str, remove_blank_text: bool = False) -> tuple[Any, str]:
    """Parse ``text``; returns (root element, original XML declaration or "").

    The editor holds Unicode text, so a declared encoding is replaced by
    UTF-8 for parsing only; the original declaration is kept for output.
    """
    match = _DECLARATION.match(text)
    declaration = match.group(1) if match else ""
    data = text
    if declaration:
        data = text.replace(declaration, _ENCODING.sub(r"\1\2UTF-8\2", declaration), 1)
    try:
        root = etree.fromstring(data.encode("utf-8"), _parser(remove_blank_text))
    except etree.XMLSyntaxError as exc:
        line, column = exc.position if exc.position else (1, 1)
        raise XmlError(str(exc.msg), int(line or 1), int(column or 0) + 1) from exc
    return root, declaration

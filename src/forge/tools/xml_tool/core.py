"""XML Tools processing (pretty print, minify, XPath) on top of forge.core.xmlsafe."""

from __future__ import annotations

from typing import Any

from lxml import etree

from forge.core.xmlsafe import XmlError, parse

__all__ = ["XmlError", "minify", "parse", "pretty", "xpath"]


def _serialize(root: Any, declaration: str, eol: str) -> str:
    body = etree.tostring(root.getroottree(), encoding="unicode", pretty_print=True)
    text = (declaration + "\n" if declaration else "") + body.rstrip("\n") + "\n"
    return text.replace("\n", eol) if eol != "\n" else text


def pretty(text: str, indent: str, eol: str = "\n") -> str:
    root, declaration = parse(text, remove_blank_text=True)
    etree.indent(root, space=indent)
    return _serialize(root, declaration, eol)


def minify(text: str) -> str:
    root, declaration = parse(text, remove_blank_text=True)
    body = etree.tostring(root.getroottree(), encoding="unicode")
    return declaration + body


def xpath(text: str, expression: str) -> list[tuple[str, int | None]]:
    """Evaluate ``expression``; returns (description, source line or None) per result.

    The default namespace, if any, is available as prefix ``d``.
    """
    root, _ = parse(text)
    namespaces = {k: v for k, v in (root.nsmap or {}).items() if k}
    if None in (root.nsmap or {}):
        namespaces.setdefault("d", root.nsmap[None])
    try:
        result = root.xpath(expression, namespaces=namespaces)
    except etree.XPathError as exc:
        raise XmlError(str(exc), 0, 0) from exc
    items = result if isinstance(result, list) else [result]
    described: list[tuple[str, int | None]] = []
    for item in items:
        if isinstance(item, etree._Element):
            tag = etree.QName(item).localname if isinstance(item.tag, str) else "comment"
            text_value = (item.text or "").strip()
            preview = f"<{tag}> {text_value[:80]}" if text_value else f"<{tag}>"
            line = item.sourceline
            described.append((preview, int(line) if isinstance(line, int) else None))
        else:
            described.append((str(item), None))
    return described

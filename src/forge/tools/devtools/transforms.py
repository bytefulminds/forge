"""Text transformations for the developer tools (no Qt): hashes, encodings,
letter case and line operations. Every function raises ValueError with a
readable message when the input cannot be converted."""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import json
import re
import urllib.parse
from collections.abc import Callable, Iterable
from pathlib import Path

HASHES: tuple[str, ...] = ("md5", "sha1", "sha256", "sha512")
HASH_LABELS = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256", "sha512": "SHA-512"}


# Hashes ---------------------------------------------------------------------------


def hash_text(text: str, algorithm: str) -> str:
    """Hex digest of ``text`` encoded as UTF-8 (what Notepad++ and most tools do)."""
    return hashlib.new(algorithm, text.encode("utf-8")).hexdigest()


def hash_file(path: Path, algorithms: Iterable[str] = HASHES) -> dict[str, str]:
    digests = {name: hashlib.new(name) for name in algorithms}
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            for digest in digests.values():
                digest.update(chunk)
    return {name: digest.hexdigest() for name, digest in digests.items()}


# Encodings --------------------------------------------------------------------------


def base64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _base64_bytes(text: str) -> bytes:
    compact = re.sub(r"\s+", "", text)
    compact += "=" * (-len(compact) % 4)
    try:
        if "-" in compact or "_" in compact:  # URL-safe alphabet (JWT and friends)
            return base64.urlsafe_b64decode(compact)
        return base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("not valid Base64") from exc


def base64_decode(text: str) -> str:
    data = _base64_bytes(text)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("the decoded data is not UTF-8 text") from exc


def url_encode(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def url_decode(text: str) -> str:
    return urllib.parse.unquote(text.replace("+", " "))


def html_escape(text: str) -> str:
    return html.escape(text, quote=True)


def html_unescape(text: str) -> str:
    return html.unescape(text)


def json_escape(text: str) -> str:
    """The text as the inside of a JSON string literal (quotes not included)."""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def json_unescape(text: str) -> str:
    source = text if text.startswith('"') and text.endswith('"') else f'"{text}"'
    try:
        value = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not a valid JSON string: {exc.msg}") from exc
    if not isinstance(value, str):
        raise ValueError("not a JSON string")
    return value


def decode_jwt(token: str) -> dict[str, object]:
    """Header and payload of a JSON Web Token (the signature is not verified)."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("a JWT has three parts separated by dots")
    try:
        header = json.loads(_base64_bytes(parts[0]))
        payload = json.loads(_base64_bytes(parts[1]))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("not a valid JWT") from exc
    return {"header": header, "payload": payload}


# Letter case ------------------------------------------------------------------------

_WORDS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def _words(text: str) -> list[str]:
    return _WORDS.findall(text)


def _per_line(convert: Callable[[str], str]) -> Callable[[str], str]:
    def apply(text: str) -> str:
        return "\n".join(convert(line) for line in text.split("\n"))

    return apply


def upper_case(text: str) -> str:
    return text.upper()


def lower_case(text: str) -> str:
    return text.lower()


def title_case(text: str) -> str:
    return re.sub(r"[^\W_]+", lambda m: m.group(0)[:1].upper() + m.group(0)[1:].lower(), text)


@_per_line
def camel_case(text: str) -> str:
    words = [w.lower() for w in _words(text)]
    return words[0] + "".join(w.capitalize() for w in words[1:]) if words else text


@_per_line
def pascal_case(text: str) -> str:
    words = _words(text)
    return "".join(w.lower().capitalize() for w in words) if words else text


@_per_line
def snake_case(text: str) -> str:
    words = _words(text)
    return "_".join(w.lower() for w in words) if words else text


@_per_line
def kebab_case(text: str) -> str:
    words = _words(text)
    return "-".join(w.lower() for w in words) if words else text


# Lines -------------------------------------------------------------------------------


def _natural_key(line: str) -> list[object]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", line)]


def sort_lines(lines: list[str], descending: bool = False) -> list[str]:
    """Natural order, without case: "file2" comes before "file10"."""
    return sorted(lines, key=_natural_key, reverse=descending)


def unique_lines(lines: list[str]) -> list[str]:
    return list(dict.fromkeys(lines))


def reverse_lines(lines: list[str]) -> list[str]:
    return lines[::-1]


def trim_trailing(lines: list[str]) -> list[str]:
    return [line.rstrip() for line in lines]

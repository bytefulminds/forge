"""UUID generation (no Qt): version 4 (random) and 7 (time ordered, RFC 9562)."""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass


def uuid7(now_ms: int | None = None) -> uuid.UUID:
    """A version 7 UUID: 48 bit Unix time in milliseconds, then random bits.
    Sorts by creation time, which keeps database indexes compact."""
    ms = int(time.time() * 1000) if now_ms is None else now_ms
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version
    value |= secrets.randbits(12) << 64
    value |= 0b10 << 62  # RFC 9562 variant
    value |= secrets.randbits(62)
    return uuid.UUID(int=value)


@dataclass(frozen=True)
class UuidOptions:
    count: int = 1
    version: int = 4  # 4 or 7
    uppercase: bool = False
    hyphens: bool = True
    braces: bool = False  # {...}, the Windows GUID notation
    separator: str = "\n"


def format_uuid(value: uuid.UUID, options: UuidOptions) -> str:
    text = str(value) if options.hyphens else value.hex
    if options.uppercase:
        text = text.upper()
    return "{" + text + "}" if options.braces else text


def generate(options: UuidOptions) -> str:
    make = uuid7 if options.version == 7 else uuid.uuid4
    count = max(1, min(options.count, 100_000))
    return options.separator.join(format_uuid(make(), options) for _ in range(count))

"""Forge design tokens.

The brand colors follow the Forge brand guide (``_assets/``, kept outside the
repository). The app never reads that folder at runtime. When the brand
palette changes, update this file.
"""

from __future__ import annotations

import colorsys
from typing import Final

# Brand palette (brand guide)
NIGHT_BLUE: Final = "#081A33"  # Primary background and dark surfaces
SKY_BLUE: Final = "#4DA3FF"  # Primary brand color and interactive elements
CYAN: Final = "#20D7E8"  # Secondary highlight
LIME: Final = "#B7FF4A"  # Accent, focus and success states (used sparingly)
LIGHT: Final = "#E6F0FF"  # Text and light backgrounds

# Helpers for derivations
WHITE: Final = "#FFFFFF"
BLACK: Final = "#000000"

# PLACEHOLDERS: semantic colors not in the brand guide yet, pending approval.
ERROR: Final = "#FF6B81"
WARNING: Final = "#FFB547"


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, round(c))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def mix(a: str, b: str, amount: float) -> str:
    """Blend color ``a`` towards ``b``; ``amount`` 0 gives ``a``, 1 gives ``b``."""
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex((ra + (rb - ra) * amount, ga + (gb - ga) * amount, ba + (bb - ba) * amount))


def shade(color: str, lightness: float) -> str:
    """Same hue and saturation as ``color`` with a new HLS ``lightness`` (0..1).

    Used for light theme accents: mixing a bright hue towards navy greys it out,
    changing only the lightness keeps it vivid.
    """
    r, g, b = (c / 255 for c in hex_to_rgb(color))
    h, _, s = colorsys.rgb_to_hls(r, g, b)
    nr, ng, nb = colorsys.hls_to_rgb(h, lightness, s)
    return rgb_to_hex((nr * 255, ng * 255, nb * 255))


def relative_luminance(color: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

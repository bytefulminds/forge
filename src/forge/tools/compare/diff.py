"""Line diff aligned for a side-by-side view, with inline changes per line pair."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Above this many lines the matcher uses its junk heuristic to stay fast.
_EXACT_LIMIT = 20_000

EQUAL = "equal"
CHANGED = "changed"
ADDED = "added"
REMOVED = "removed"
FILLER = "filler"


@dataclass
class Row:
    text: str
    number: int | None  # 1-based line number in its document; None for filler
    kind: str
    inline: list[tuple[int, int]] = field(default_factory=list)  # changed char ranges


@dataclass
class Comparison:
    left: list[Row]
    right: list[Row]
    blocks: list[int]  # first row of every difference
    changed: int = 0
    added: int = 0
    removed: int = 0

    @property
    def identical(self) -> bool:
        return not self.blocks


def _inline(a: str, b: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    left: list[tuple[int, int]] = []
    right: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if i2 > i1:
            left.append((i1, i2))
        if j2 > j1:
            right.append((j1, j2))
    return left, right


def compare(left_text: str, right_text: str) -> Comparison:
    a = left_text.splitlines()
    b = right_text.splitlines()
    exact = max(len(a), len(b)) <= _EXACT_LIMIT
    matcher = SequenceMatcher(None, a, b, autojunk=not exact)
    result = Comparison([], [], [])
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                result.left.append(Row(a[i1 + offset], i1 + offset + 1, EQUAL))
                result.right.append(Row(b[j1 + offset], j1 + offset + 1, EQUAL))
            continue
        result.blocks.append(len(result.left))
        left_count, right_count = i2 - i1, j2 - j1
        for k in range(max(left_count, right_count)):
            has_left, has_right = k < left_count, k < right_count
            if has_left and has_right:
                la, rb = a[i1 + k], b[j1 + k]
                inline_left, inline_right = _inline(la, rb)
                result.left.append(Row(la, i1 + k + 1, CHANGED, inline_left))
                result.right.append(Row(rb, j1 + k + 1, CHANGED, inline_right))
                result.changed += 1
            elif has_left:
                result.left.append(Row(a[i1 + k], i1 + k + 1, REMOVED))
                result.right.append(Row("", None, FILLER))
                result.removed += 1
            else:
                result.left.append(Row("", None, FILLER))
                result.right.append(Row(b[j1 + k], j1 + k + 1, ADDED))
                result.added += 1
    return result

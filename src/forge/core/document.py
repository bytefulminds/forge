"""Document model: everything Forge knows about an open buffer except its text."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

from forge.core.encoding import DEFAULT_ENCODING, TextEncoding
from forge.core.eol import DEFAULT_EOL, Eol

_ids = itertools.count(1)


@dataclass
class Document:
    path: Path | None = None
    encoding: TextEncoding = DEFAULT_ENCODING
    # Read at creation time, so tests can pin it (see tests/conftest.py).
    eol: Eol = field(default_factory=lambda: DEFAULT_EOL)
    untitled_index: int = 0
    id: int = field(default_factory=lambda: next(_ids))

    @property
    def is_untitled(self) -> bool:
        return self.path is None

    @property
    def display_name(self) -> str:
        if self.path is not None:
            return self.path.name
        return f"new {self.untitled_index}"

"""Application logging to a rotating file in the platform log directory."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from forge.core import paths

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger("forge")
    if root.handlers:
        return
    root.setLevel(level)
    handler = RotatingFileHandler(
        paths.log_dir() / "forge.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)

"""Reading and atomically writing text files."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from forge.core.encoding import TextEncoding, decode, detect_encoding, encode
from forge.core.eol import Eol, detect_eol


@dataclass(frozen=True)
class LoadedText:
    text: str
    encoding: TextEncoding
    eol: Eol


def load_text(path: Path) -> LoadedText:
    data = path.read_bytes()
    encoding = detect_encoding(data)
    text = decode(data, encoding)
    return LoadedText(text=text, encoding=encoding, eol=detect_eol(text))


def save_text(path: Path, text: str, encoding: TextEncoding) -> None:
    """Write ``text`` to ``path`` atomically (temp file + rename).

    A crash or full disk never leaves a half written file behind. Existing file
    permissions are preserved.
    """
    data = encode(text, encoding)
    path = path.resolve()
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".forge-tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

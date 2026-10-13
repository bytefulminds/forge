"""Reading and atomically writing text files."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
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


@dataclass(frozen=True)
class LoadedBytes:
    """A file prepared for the editor: UTF-8 bytes (Scintilla's own format)."""

    utf8: bytes
    encoding: TextEncoding
    eol: Eol


def load_utf8(path: Path) -> LoadedBytes:
    """Read ``path`` and return its content as UTF-8 bytes.

    Used for large files: a UTF-8 file without BOM is only validated, not
    converted, so a 100 MB file never exists as a Python string.
    """
    data = path.read_bytes()
    encoding = detect_encoding(data)
    if encoding.codec == "utf-8" and not encoding.bom:
        data.decode("utf-8")  # validate; raises UnicodeDecodeError if invalid
        utf8 = data
    else:
        utf8 = decode(data, encoding).encode("utf-8")
    sample = utf8[:1_000_000].decode("utf-8", errors="ignore")
    return LoadedBytes(utf8=utf8, encoding=encoding, eol=detect_eol(sample))


# Windows refuses to replace a file another program briefly holds open (virus
# scanners, search indexers, cloud sync): try again for about a second.
_REPLACE_ATTEMPTS = 20
_REPLACE_WAIT_SECONDS = 0.05


def _replace(source: Path, target: Path) -> None:
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_WAIT_SECONDS)


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
        _replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

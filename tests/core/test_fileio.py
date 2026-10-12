from __future__ import annotations

import os
import stat
from pathlib import Path

from forge.core.encoding import UTF16_LE, TextEncoding
from forge.core.eol import Eol
from forge.core.fileio import load_text, save_text


def test_load_detects_encoding_and_eol(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes("één\r\ntwee\r\n".encode("utf-16-le").join([b"\xff\xfe", b""]))
    loaded = load_text(path)
    assert loaded.encoding == TextEncoding(UTF16_LE, bom=True)
    assert loaded.eol is Eol.CRLF
    assert loaded.text == "één\r\ntwee\r\n"


def test_save_preserves_encoding_and_bom(tmp_path: Path) -> None:
    path = tmp_path / "b.txt"
    encoding = TextEncoding("utf-8", bom=True)
    save_text(path, "hallo\n", encoding)
    assert path.read_bytes() == b"\xef\xbb\xbfhallo\n"
    assert load_text(path).encoding == encoding


def test_save_is_atomic_and_keeps_permissions(tmp_path: Path) -> None:
    path = tmp_path / "script.sh"
    path.write_text("old\n")
    os.chmod(path, 0o750)
    save_text(path, "new\n", TextEncoding())
    assert path.read_text() == "new\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o750
    assert [p.name for p in tmp_path.iterdir()] == ["script.sh"]

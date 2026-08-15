"""Atomic file writes via tempfile + fsync + os.replace.

Writes to a sibling temp file, fsyncs it, then ``os.replace`` swaps it into
place. On any failure, the temp file is removed and the target is left
untouched.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

__all__ = ["atomic_write_bytes", "atomic_write_text"]


def atomic_write_text(
    path: Path,
    data: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o644,
) -> None:
    """Write ``data`` to ``path`` atomically.

    If ``path`` already exists, its current permission bits are preserved on
    the replacement file. Otherwise the new file is created with ``mode``.
    """
    target_mode = path.stat().st_mode & 0o777 if path.exists() else mode
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, target_mode)
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically.

    Binary sibling of :func:`atomic_write_text`. If ``path`` already exists,
    its current permission bits are preserved on the replacement file.
    Otherwise the new file is created with mode ``0o644``.
    """
    target_mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, target_mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

"""Atomic file writes via tempfile + fsync + os.replace.

Writes to a sibling temp file, fsyncs it, then ``os.replace`` swaps it into
place. On any failure, the temp file is removed and the target is left
untouched.

The rename itself is not fsynced: only the temp file's contents are, so the
rename is not guaranteed durable across a power loss. ``os.replace`` also
swaps a new inode into ``path`` itself rather than following a symlink or
hardlink, so writing to a symlinked or hardlinked path leaves a plain file
at that path and the original link target stale.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

__all__ = ["atomic_write_bytes", "atomic_write_text"]


def _atomic_write(
    path: Path,
    data: str | bytes,
    file_mode: str,
    encoding: str | None,
    default_mode: int,
) -> None:
    """Write ``data`` to ``path`` atomically.

    Shared body for :func:`atomic_write_text` and :func:`atomic_write_bytes`.
    """
    try:
        target_mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        target_mode = default_mode
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(fd, target_mode)
            except BaseException:
                os.close(fd)
                raise
        with os.fdopen(fd, file_mode, encoding=encoding) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # A cleanup failure must never replace the original write error.
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


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
    _atomic_write(path, data, "w", encoding, mode)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically.

    Binary sibling of :func:`atomic_write_text`. If ``path`` already exists,
    its current permission bits are preserved on the replacement file.
    Otherwise the new file is created with mode ``0o644``.
    """
    _atomic_write(path, data, "wb", None, 0o644)

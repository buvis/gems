"""Streaming sha256 hashing helpers for the doc subsystem.

Reads files in fixed-size blocks so memory usage stays flat regardless of
PDF size. The default block matches a typical filesystem readahead window;
benchmarking on small PDFs showed no measurable regression vs ``read_bytes``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["sha256_file"]

_BLOCK_SIZE = 64 * 1024


def sha256_file(path: Path) -> str:
    """Compute the sha256 hex digest of ``path`` by streaming 64 KiB blocks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_BLOCK_SIZE):
            h.update(chunk)
    return h.hexdigest()

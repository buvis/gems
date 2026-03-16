"""Symlink-safe recursive globbing utilities."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def is_safe_path(candidate: Path, allowed_bases: list[Path]) -> bool:
    """Reject symlinks pointing outside expected directories.

    Args:
        candidate: Path to validate (may be symlink).
        allowed_bases: Directories the resolved path must be under.

    Returns:
        True if resolved path is under one of allowed_bases and exists.
    """
    try:
        # Check broken symlinks
        if candidate.is_symlink() and not candidate.exists():
            return False

        resolved = candidate.resolve()
        for base in allowed_bases:
            try:
                resolved.relative_to(base.resolve())
                return True
            except ValueError:
                continue
        return False
    except (OSError, RuntimeError):
        return False


def safe_rglob(directory: Path, pattern: str = "*") -> Iterator[Path]:
    """Recursively glob, skipping paths resolving outside directory.

    Args:
        directory: Base directory for traversal.
        pattern: Glob pattern (default "*").

    Yields:
        Paths that resolve within directory.
    """
    allowed = [directory.resolve()]
    for path in directory.rglob(pattern):
        if is_safe_path(path, allowed):
            yield path

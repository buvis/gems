from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FileEntry", "BranchInfo"]


@dataclass(frozen=True, slots=True)
class FileEntry:
    """A file with its git status and secret flag."""

    path: str
    status: str
    is_secret: bool = False


@dataclass(frozen=True, slots=True)
class BranchInfo:
    """Branch metadata for the status bar."""

    name: str
    ahead: int = 0
    behind: int = 0
    secret_count: int = 0

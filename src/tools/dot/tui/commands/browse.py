from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dot.git.service import DotGitService

__all__ = ["DirEntry", "TrackingStatus", "get_tracking_status", "list_directory"]


class TrackingStatus(enum.Enum):
    TRACKED = "tracked"
    UNTRACKED = "untracked"
    IGNORED = "ignored"


@dataclass(frozen=True)
class DirEntry:
    name: str
    path: str
    is_dir: bool
    status: TrackingStatus


def _query_git_sets(git_ops: DotGitService, rel_query: str) -> tuple[set[str], set[str]]:
    """Return (tracked, ignored) relative path sets for a directory."""
    tracked = git_ops.ls_files(rel_query)
    ignored = git_ops.check_ignore(f"{rel_query}/*")
    return tracked, ignored


def list_directory(git_ops: DotGitService, path: str) -> list[DirEntry]:
    """List directory contents with git tracking status."""
    p = Path(path)

    children = sorted(p.iterdir(), key=lambda x: x.name)

    # At dotfiles_root, show only dotfiles when dotfiles are present
    if path == git_ops.dotfiles_root:
        dotfiles = [c for c in children if c.name.startswith(".")]
        if dotfiles:
            children = dotfiles

    # Build relative paths for batch git queries
    rel_paths = []
    for child in children:
        try:
            rel_path = child.relative_to(git_ops.wd)
            rel_paths.append(str(rel_path))
        except ValueError:
            rel_paths.append(child.name)

    # Relative query path for batch git commands
    try:
        rel_query = str(Path(path).relative_to(git_ops.wd))
    except ValueError:
        rel_query = "."

    tracked, ignored = _query_git_sets(git_ops, rel_query) if rel_paths else (set(), set())

    entries: list[DirEntry] = []

    # Add parent entry unless at filesystem root
    if path != "/":
        entries.append(
            DirEntry(
                name="..",
                path=str(p.parent),
                is_dir=True,
                status=TrackingStatus.UNTRACKED,
            )
        )

    for child, rel in zip(children, rel_paths):
        if rel in tracked:
            status = TrackingStatus.TRACKED
        elif rel in ignored:
            status = TrackingStatus.IGNORED
        else:
            status = TrackingStatus.UNTRACKED

        entries.append(
            DirEntry(
                name=child.name,
                path=str(child),
                is_dir=child.is_dir(),
                status=status,
            )
        )

    return entries


def get_tracking_status(git_ops: DotGitService, path: str) -> TrackingStatus:
    """Check tracking status for a single path."""
    tracked = git_ops.ls_files(path)
    if path in tracked:
        return TrackingStatus.TRACKED

    ignored = git_ops.check_ignore(path)
    if path in ignored:
        return TrackingStatus.IGNORED

    return TrackingStatus.UNTRACKED

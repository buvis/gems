from __future__ import annotations

import enum
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dot.tui.git_ops import GitOps

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


def _query_git_sets(git_ops: GitOps, rel_query: str) -> tuple[set[str], set[str]]:
    """Return (tracked, ignored) relative path sets for a directory."""
    tracked: set[str] = set()
    err, out = git_ops.shell.exe(f"cfg ls-files {shlex.quote(rel_query)}", git_ops.wd)
    if not err and out and out.strip():
        tracked = {line for line in out.strip().split("\n") if line}

    ignored: set[str] = set()
    err, out = git_ops.shell.exe(f"cfg check-ignore {shlex.quote(rel_query)}/*", git_ops.wd)
    if not err and out and out.strip():
        ignored = {line for line in out.strip().split("\n") if line}

    return tracked, ignored


def list_directory(git_ops: GitOps, path: str) -> list[DirEntry]:
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
            rel = child.relative_to(git_ops.wd)
            rel_paths.append(str(rel))
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


def get_tracking_status(git_ops: GitOps, path: str) -> TrackingStatus:
    """Check tracking status for a single path."""
    err, out = git_ops.shell.exe(f"cfg ls-files {shlex.quote(path)}", git_ops.wd)
    if not err and out and path in out:
        return TrackingStatus.TRACKED

    err, out = git_ops.shell.exe(f"cfg check-ignore {shlex.quote(path)}", git_ops.wd)
    if not err and out and path in out:
        return TrackingStatus.IGNORED

    return TrackingStatus.UNTRACKED

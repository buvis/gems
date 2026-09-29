"""Pure filesystem signal readers for a repository checkout.

These read only the local working tree (no subprocess, no network): the PRD
pipeline, the CHANGELOG ``[Unreleased]`` state, the brush-hygiene report date,
and the purge/trash cadence. Kept in the domain layer because they are pure
logic with no UI dependency.

Project-management artifacts migrated from a repo's ``dev/local/`` scratch area
into a tracked ``docs/dev/`` tree (the ``brief-portfolio`` skill migration). Each
reader therefore resolves the migrated ``docs/dev/`` location first and falls
back to the legacy ``dev/local/`` location, so both migrated and not-yet-migrated
repos report correctly. The precedence lives in one shared helper,
:func:`_resolve_location`, so every reader shares one rule.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from postup.domain.contracts import PrdPipeline, WipPrd

__all__ = [
    "read_brush_last_run",
    "read_changelog_unreleased",
    "read_prd_pipeline",
    "read_purge_last_run",
]

_BRUSH_RE = re.compile(r"^\s*-?\s*generated:\s*(\d{4}-\d{2}-\d{2})")
_DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _resolve_location(repo: Path, new_rel: str, legacy_rel: str) -> Path:
    """Resolve a project-management path, preferring the migrated location.

    Args:
        repo: Repository working-tree root.
        new_rel: The migrated ``docs/dev/`` relative location.
        legacy_rel: The pre-migration ``dev/local/`` relative location.

    Returns:
        The migrated path when it exists on disk; otherwise the legacy path.
        A mid-migration repo (both present) resolves to the migrated one, and a
        repo with neither resolves to the migrated path so the caller's own
        absent-target handling yields the empty/``None`` result unchanged.
    """
    new_path = repo / new_rel
    if new_path.exists():
        return new_path
    legacy_path = repo / legacy_rel
    if legacy_path.exists():
        return legacy_path
    return new_path


def _idle_days(path: Path) -> int:
    """Return whole days since ``path`` was last modified (clamped at 0)."""
    age = (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) // 86400
    return max(0, int(age))


def _first_title(path: Path) -> str:
    """Return the first Markdown ``# `` heading in ``path``, else its stem."""
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def read_prd_pipeline(repo: Path) -> PrdPipeline:
    """Read PRD counts under the project-management ``prds/{backlog,wip,done}`` tree.

    Prefers the migrated ``docs/dev/project-management/prds`` location, falling
    back to the legacy ``dev/local/prds`` location when the migrated one is
    absent.

    Args:
        repo: Repository working-tree root.

    Returns:
        Backlog titles, WIP entries with idle age, and the done count. An absent
        ``prds`` tree yields empty sections.
    """
    base = _resolve_location(repo, "docs/dev/project-management/prds", "dev/local/prds")

    def markdown_files(sub: str) -> list[Path]:
        directory = base / sub
        return sorted(directory.glob("*.md")) if directory.is_dir() else []

    backlog = [_first_title(f) for f in markdown_files("backlog")]
    wip = [WipPrd(title=_first_title(f), idle_days=_idle_days(f)) for f in markdown_files("wip")]
    done_count = len(markdown_files("done"))
    return PrdPipeline(backlog=backlog, wip=wip, done_count=done_count)


def read_changelog_unreleased(repo: Path) -> bool | None:
    """Return whether the CHANGELOG ``[Unreleased]`` section has bullet entries.

    Args:
        repo: Repository working-tree root.

    Returns:
        ``True``/``False`` when a ``CHANGELOG.md`` exists (has/lacks bullets in
        its unreleased section); ``None`` when there is no CHANGELOG.
    """
    changelog = repo / "CHANGELOG.md"
    if not changelog.is_file():
        return None
    in_unreleased = False
    for line in changelog.read_text(errors="replace").splitlines():
        if line.startswith("## "):
            in_unreleased = "unreleased" in line.lower()
        elif in_unreleased and line.lstrip().startswith(("- ", "* ")):
            return True
    return False


def read_brush_last_run(repo: Path) -> str | None:
    """Return the brush-report ``generated:`` date (ISO day), or ``None``.

    Prefers the migrated ``docs/dev/project-management/audit-results/brush-report.md``
    location, falling back to the legacy
    ``dev/local/audit-results/brush-report.md`` when the migrated one is absent.

    Args:
        repo: Repository working-tree root.

    Returns:
        The ``YYYY-MM-DD`` date from the brush report, or ``None`` when the
        report is absent or carries no date.
    """
    report = _resolve_location(
        repo,
        "docs/dev/project-management/audit-results/brush-report.md",
        "dev/local/audit-results/brush-report.md",
    )
    if not report.is_file():
        return None
    for line in report.read_text(errors="replace").splitlines():
        match = _BRUSH_RE.match(line)
        if match:
            return match.group(1)
    return None


def read_purge_last_run(repo: Path) -> str | None:
    """Return the newest dated trash-subdirectory name (ISO day), or ``None``.

    The purge/trash cadence signal: the migrated skill parks removed scratch
    under a dated ``YYYY-MM-DD`` subdirectory of its trash dir, so the newest
    such subdirectory *name* is the last purge date. This is a name-based signal,
    not an mtime one. Prefers the migrated ``docs/dev/tmp/.trash`` location,
    falling back to the legacy ``dev/local/.trash`` when the migrated one is
    absent.

    Args:
        repo: Repository working-tree root.

    Returns:
        The newest ``YYYY-MM-DD`` subdirectory name under the trash dir, or
        ``None`` when the trash dir is absent or holds no dated subdirectory.
    """
    trash = _resolve_location(repo, "docs/dev/tmp/.trash", "dev/local/.trash")
    if not trash.is_dir():
        return None
    return max(
        (entry.name for entry in trash.iterdir() if entry.is_dir() and _DATE_DIR_RE.match(entry.name)),
        default=None,
    )

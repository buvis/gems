"""Pure filesystem signal readers for a repository checkout.

These read only the local working tree (no subprocess, no network): the PRD
pipeline under ``dev/local/prds``, the CHANGELOG ``[Unreleased]`` state, and
the brush-hygiene report date. Kept in the domain layer because they are pure
logic with no UI dependency.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from postup.domain.contracts import PrdPipeline, WipPrd

__all__ = ["read_brush_last_run", "read_changelog_unreleased", "read_prd_pipeline"]

_BRUSH_RE = re.compile(r"^\s*-?\s*generated:\s*(\d{4}-\d{2}-\d{2})")


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
    """Read PRD counts under ``dev/local/prds/{backlog,wip,done}``.

    Args:
        repo: Repository working-tree root.

    Returns:
        Backlog titles, WIP entries with idle age, and the done count. An absent
        ``prds`` tree yields empty sections.
    """
    base = repo / "dev" / "local" / "prds"

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

    Args:
        repo: Repository working-tree root.

    Returns:
        The ``YYYY-MM-DD`` date from ``dev/local/audit-results/brush-report.md``,
        or ``None`` when the report is absent or carries no date.
    """
    report = repo / "dev" / "local" / "audit-results" / "brush-report.md"
    if not report.is_file():
        return None
    for line in report.read_text(errors="replace").splitlines():
        match = _BRUSH_RE.match(line)
        if match:
            return match.group(1)
    return None

"""Host-link rescue for pull operations.

Implements pre-merge rescue of host-link targets that would be deleted by
incoming commits. Supports moves (target exists, source missing), duplicates
(identical bytes), and collisions (different bytes, user must choose).
"""

from __future__ import annotations

import dataclasses
import enum
import filecmp
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.hostlinks.manifest import MANIFEST_PATH, HostLink, parse_manifest

if TYPE_CHECKING:
    from dot.git.service import DotGitService

__all__ = [
    "RescuePlan",
    "Resolution",
    "apply_rescue",
    "plan_rescue",
]


class Resolution(enum.StrEnum):
    """Resolution choice for a host-link collision."""

    KEEP_SOURCE = "keep-source"
    KEEP_TARGET = "keep-target"
    CANCEL = "cancel"


@dataclasses.dataclass
class RescuePlan:
    """Plan for pre-merge rescue of host-link targets.

    Attributes:
        moves: Entries where target exists but source is missing.
        duplicates: Entries where target and source have identical bytes.
        collisions: Entries where target and source differ (or one is a dir).
        skipped: Reason rescue was skipped, or None if planned successfully.
        error: Error that prevented planning, or None.
    """

    moves: list[HostLink] = dataclasses.field(default_factory=list)
    duplicates: list[HostLink] = dataclasses.field(default_factory=list)
    collisions: list[HostLink] = dataclasses.field(default_factory=list)
    skipped: str | None = None
    error: str | None = None


def _classify_entry(root: Path, link: HostLink) -> str | None:
    """Classify a deletion-affected entry.

    Returns one of "move", "duplicate", "collision", or None (ignore when the
    target is already missing or already a link).
    """
    target_path = root / link.target
    source_path = root / link.source

    if not target_path.exists() or target_path.is_symlink():
        return None
    if not source_path.exists():
        return "move"
    if target_path.is_file() and source_path.is_file():
        if filecmp.cmp(target_path, source_path, shallow=False):
            return "duplicate"
        return "collision"
    # At least one side is a directory.
    return "collision"


def plan_rescue(root: Path, git_service: DotGitService) -> RescuePlan:
    """Plan the pre-merge rescue for host-link targets.

    Args:
        root: Dotfiles root directory.
        git_service: Initialized DotGitService (after fetch()).

    Returns:
        A RescuePlan describing what needs to happen.
    """
    if not git_service.has_upstream():
        return RescuePlan(skipped="pull rescue skipped: no upstream branch")

    upstream_text = git_service.show_upstream_file(MANIFEST_PATH) or ""
    upstream_links, _errors = parse_manifest(upstream_text)
    upstream_by_target = {link.target: link for link in upstream_links}
    deleted_paths = set(git_service.upstream_deleted_paths())

    buckets: dict[str, list[HostLink]] = {"move": [], "duplicate": [], "collision": []}

    for deleted in deleted_paths:
        for target, link in upstream_by_target.items():
            if deleted != target and not deleted.startswith(target + "/"):
                continue
            kind = _classify_entry(root, link)
            if kind is not None and link not in buckets[kind]:
                buckets[kind].append(link)
            break

    return RescuePlan(
        moves=buckets["move"],
        duplicates=buckets["duplicate"],
        collisions=buckets["collision"],
    )


def _backup_path(root: Path, source: str, timestamp: str) -> Path:
    """Return the timestamped backup path for a source entry."""
    source_path = root / source
    return source_path.parent / f"{source_path.name}.dot-{timestamp}"


def _apply_collision(root: Path, entry: HostLink, backup_path: Path, resolution: Resolution) -> str | None:
    """Apply one resolved collision; return its info line, or None for no-op."""
    target_path = root / entry.target
    source_path = root / entry.source

    if resolution == Resolution.KEEP_SOURCE:
        shutil.move(str(target_path), str(backup_path))
        return f"kept {entry.source}, moved {entry.target} to {backup_path.name}"
    if resolution == Resolution.KEEP_TARGET:
        shutil.move(str(source_path), str(backup_path))
        shutil.move(str(target_path), str(source_path))
        return f"kept {entry.target} as {entry.source}, moved old source to {backup_path.name}"
    return None


def apply_rescue(
    root: Path,
    plan: RescuePlan,
    resolutions: dict[str, Resolution] | None = None,
) -> CommandResult:
    """Apply the rescue plan.

    Args:
        root: Dotfiles root directory.
        plan: The rescue plan from plan_rescue().
        resolutions: Resolution choices keyed by target for collisions.

    Returns:
        CommandResult with info lines describing actions taken.
    """
    resolutions = resolutions or {}

    # Any collision without a concrete keep-choice (missing or CANCEL) aborts.
    unresolved = [
        entry.target for entry in plan.collisions if resolutions.get(entry.target) in (None, Resolution.CANCEL)
    ]
    if unresolved:
        return CommandResult(
            success=False,
            error=f"pull stopped: unresolved host-link collision(s): {', '.join(unresolved)}",
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Pre-check: refuse before any change if a backup path already exists.
    for entry in plan.collisions:
        backup_path = _backup_path(root, entry.source, timestamp)
        if backup_path.exists():
            return CommandResult(
                success=False,
                error=f"backup path already exists: {backup_path}",
            )

    info: list[str] = []

    # Moves: relocate the real file to its source location.
    for entry in plan.moves:
        source_path = root / entry.source
        source_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root / entry.target), str(source_path))
        info.append(f"rescued {entry.target} to {entry.source}")

    # Duplicates: drop the target; the source already holds identical bytes.
    for entry in plan.duplicates:
        target_path = root / entry.target
        if target_path.is_dir():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
        info.append(f"rescued {entry.target} to {entry.source}")

    # Collisions: apply the user's resolution.
    for entry in plan.collisions:
        backup_path = _backup_path(root, entry.source, timestamp)
        line = _apply_collision(root, entry, backup_path, resolutions[entry.target])
        if line is not None:
            info.append(line)

    return CommandResult(success=True, info=info)

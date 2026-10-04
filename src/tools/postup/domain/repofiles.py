"""Pure filesystem signal readers for a repository checkout.

These read only the local working tree (no subprocess, no network): the PRD
pipeline, the CHANGELOG ``[Unreleased]`` state, the brush-hygiene report date,
and the purge/trash cadence. Kept in the domain layer because they are pure
logic with no UI dependency.

Project-management artifacts migrated from a repo's ``dev/local/`` scratch area
into a tracked ``docs/dev/`` tree (the ``brief-portfolio`` skill migration), and
the PRD queue itself was then reorganized from flat
``prds/{backlog,wip,done}/*.md`` files into per-spec *bundles* under
``specs/NNNNN-title/`` -- each bundle carrying ``requirements.md``, ``design.md``,
``tasks.md`` and a ``.specflow.json`` that holds the authoritative lifecycle
state. Each reader resolves the newest known location first and falls back
through the older ones, so a repo at any migration stage still reports. The
precedence lives in one shared helper, :func:`_resolve_location`, so every reader
shares one rule.
"""

from __future__ import annotations

import json
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


def _resolve_location(repo: Path, *candidates: str) -> Path:
    """Resolve a project-management path from ordered location candidates.

    Args:
        repo: Repository working-tree root.
        *candidates: Relative locations in precedence order, newest first (e.g.
            the migrated ``specs/`` bundle tree, then the legacy
            ``prds/{backlog,wip,done}`` tree, then the pre-migration
            ``dev/local/`` tree).

    Returns:
        The first candidate that exists on disk. When none exist, the first
        (newest) candidate is returned so the caller's own absent-target
        handling yields the empty/``None`` result unchanged. ``candidates`` must
        be non-empty.
    """
    for rel in candidates:
        path = repo / rel
        if path.exists():
            return path
    return repo / candidates[0]


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


# Spec-bundle lifecycle phases that count as actively in progress (WIP). A bundle
# whose ``.specflow.json`` phase is one of these -- and that is not parked by
# ``hold`` -- is reported as a WIP PRD with its idle age.
_WIP_PHASES = frozenset({"requirements", "design", "tasks", "implementing"})
_COMPLETED_PHASE = "completed"


def _bundle_title(bundle: Path) -> str:
    """Return a spec bundle's title: first ``# `` heading of requirements.md else dir name."""
    requirements = bundle / "requirements.md"
    if requirements.is_file():
        return _first_title(requirements)
    return bundle.name


def _bundle_idle_days(bundle: Path) -> int:
    """Return idle age for a WIP bundle.

    Mirrors the legacy flat-file ``_idle_days`` intent (whole days since last
    touch) but over a bundle: the newest mtime among the bundle directory and
    its ``.specflow.json`` state file, so re-touching the state (a phase change)
    resets idleness just as rewriting a flat PRD file used to.
    """
    mtimes = [bundle.stat().st_mtime]
    state = bundle / ".specflow.json"
    if state.is_file():
        mtimes.append(state.stat().st_mtime)
    newest = max(mtimes)
    age = (datetime.now(timezone.utc).timestamp() - newest) // 86400
    return max(0, int(age))


def _pipeline_from_bundles(specs: Path) -> PrdPipeline:
    """Derive a :class:`PrdPipeline` from a ``specs/NNNNN-title/`` bundle tree.

    State is read from each bundle's ``.specflow.json`` (never a parent
    directory). The honest phase/hold -> bucket mapping is:

    * ``hold == true`` -> **backlog** (the bundle is parked; this wins over the
      phase string, since a held bundle is not making progress).
    * phase ``completed`` -> **done_count**.
    * phase in ``{requirements, design, tasks, implementing}`` -> **wip**, as a
      :class:`WipPrd` carrying the bundle's idle age.
    * phase ``not-started`` (or any unrecognized / missing phase) -> **backlog**;
      a bundle that exists but is neither active nor done is waiting.

    Bundles are the immediate subdirectories of ``specs`` that carry a
    ``.specflow.json``; other entries are ignored. Backlog and WIP are ordered by
    bundle directory name for a stable, deterministic report.
    """
    bundles = sorted(
        (d for d in specs.iterdir() if d.is_dir() and (d / ".specflow.json").is_file()),
        key=lambda d: d.name,
    )
    backlog: list[str] = []
    wip: list[WipPrd] = []
    done_count = 0
    for bundle in bundles:
        try:
            state = json.loads((bundle / ".specflow.json").read_text(errors="replace"))
        except (ValueError, OSError):
            state = {}
        held = bool(state.get("hold"))
        phase = state.get("phase")
        if held:
            backlog.append(_bundle_title(bundle))
        elif phase == _COMPLETED_PHASE:
            done_count += 1
        elif phase in _WIP_PHASES:
            wip.append(WipPrd(title=_bundle_title(bundle), idle_days=_bundle_idle_days(bundle)))
        else:
            # not-started, or an unknown/missing phase: waiting in backlog.
            backlog.append(_bundle_title(bundle))
    return PrdPipeline(backlog=backlog, wip=wip, done_count=done_count)


def _pipeline_from_flat_prds(base: Path) -> PrdPipeline:
    """Derive a :class:`PrdPipeline` from the legacy flat ``{backlog,wip,done}`` tree.

    Preserves the pre-bundle behavior exactly: ``*.md`` files under ``backlog``
    and ``wip`` keyed by their first ``# `` heading (else stem), ``done`` counted
    by file.
    """

    def markdown_files(sub: str) -> list[Path]:
        directory = base / sub
        return sorted(directory.glob("*.md")) if directory.is_dir() else []

    backlog = [_first_title(f) for f in markdown_files("backlog")]
    wip = [WipPrd(title=_first_title(f), idle_days=_idle_days(f)) for f in markdown_files("wip")]
    done_count = len(markdown_files("done"))
    return PrdPipeline(backlog=backlog, wip=wip, done_count=done_count)


def read_prd_pipeline(repo: Path) -> PrdPipeline:
    """Read the PRD pipeline from the project-management spec/PRD tree.

    Precedence (newest layout first, so a repo at any migration stage reports):

    1. ``docs/dev/project-management/specs`` -- the migrated spec-*bundle* tree,
       where each ``NNNNN-title/`` bundle's ``.specflow.json`` is the source of
       truth for its lifecycle phase and hold state. Read via
       :func:`_pipeline_from_bundles` (see it for the phase/hold -> bucket map).
    2. ``docs/dev/project-management/prds`` -- the legacy flat
       ``{backlog,wip,done}/*.md`` tree (migrated location).
    3. ``dev/local/prds`` -- the legacy flat tree in the pre-migration scratch
       location.

    Layouts 2 and 3 share the unchanged dir-name behavior
    (:func:`_pipeline_from_flat_prds`).

    Args:
        repo: Repository working-tree root.

    Returns:
        Backlog titles, WIP entries with idle age, and the done count. An absent
        tree yields empty sections.
    """
    specs = repo / "docs/dev/project-management/specs"
    if specs.is_dir():
        return _pipeline_from_bundles(specs)
    base = _resolve_location(repo, "docs/dev/project-management/prds", "dev/local/prds")
    return _pipeline_from_flat_prds(base)


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

    The audit-results area was consolidated into ``reviews/``, so this prefers
    the migrated ``docs/dev/project-management/reviews/brush-report.md`` location
    and falls back to the legacy ``dev/local/audit-results/brush-report.md`` when
    it is absent.

    Args:
        repo: Repository working-tree root.

    Returns:
        The ``YYYY-MM-DD`` date from the brush report, or ``None`` when the
        report is absent or carries no date.
    """
    report = _resolve_location(
        repo,
        "docs/dev/project-management/reviews/brush-report.md",
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

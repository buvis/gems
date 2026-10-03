"""Orchestrate one source end to end, and the bounded inbox sweep.

``ingest_source`` turns a single source document into committed zettels via the
one-call loop (PRD "Per-source pipeline"): resolve the archive path up front
(archive-first), assemble the prompt (source + voice + split rule + claim set),
one backend call, render drafts, resolve conflicts and corroborations, author
MOCs, stage the whole set, and apply it as one scoped commit — or leave the
vault untouched on any failure.

``sweep_sources`` picks the work and bounds it (PRD "Inbox sweep and run
bounds"): at most ``max_sources_per_run`` sources in filename order, each under
``source_timeout_seconds`` of wall clock, the remainder deferred and named for
the trail. ``dry_run`` runs the backend and reports what would land without
applying anything.

No console, no Click here; :class:`klyreon.commands.ingest.CommandIngest` wraps
this for the CLI.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from klyreon.backends.base import Backend, BackendError, IngestPayload
from klyreon.ingest.conflicts import EditedZettel, apply_conflicts, apply_corroborations
from klyreon.ingest.moc import ensure_moc
from klyreon.ingest.render import RenderedZettel, RenderError, render_zettels
from klyreon.prompts import assemble_prompt, load_voice
from klyreon.run.staging import Staging, StagingError
from klyreon.spec.model import Document, FileKind
from klyreon.spec.parser import FrontmatterError, parse_file
from klyreon.spec.writer import serialize
from klyreon.vault.git import GitIdentity

__all__ = [
    "SourceOutcome",
    "SourceStatus",
    "SweepResult",
    "ingest_source",
    "sweep_sources",
]


class SourceStatus(str, Enum):
    """How one source's ingest ended."""

    COMMITTED = "committed"
    FAILED = "failed"
    DRY_RUN = "dry-run"


@dataclass(slots=True)
class SourceOutcome:
    """The result of ingesting one source."""

    source: str
    status: SourceStatus
    zettels_created: list[str] = field(default_factory=list)
    conflict_lines: list[str] = field(default_factory=list)
    corroboration_lines: list[str] = field(default_factory=list)
    mocs_touched: list[str] = field(default_factory=list)
    commit_sha: str | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SweepResult:
    """The result of one ingest run over the inbox."""

    committed: list[SourceOutcome] = field(default_factory=list)
    failed: list[SourceOutcome] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    dry_run: list[SourceOutcome] = field(default_factory=list)

    @property
    def any_failed(self) -> bool:
        return bool(self.failed)


def _archive_path_for(source_rel: str) -> str:
    """Resolve the archive-first destination for an inbox source path.

    ``sources/YYYY-MM/<name>.md`` -> ``sources/archive/YYYY-MM/<name>.md``.
    """
    parts = Path(source_rel).parts
    # parts like ("sources", "YYYY-MM", "name.md")
    if len(parts) >= 3 and parts[0] == "sources" and parts[1] != "archive":
        return str(Path("sources", "archive", *parts[1:]))
    # Fallback: nest under archive preserving the final two components.
    name = Path(source_rel).name
    month = Path(source_rel).parent.name or dt.datetime.now().astimezone().strftime("%Y-%m")
    return str(Path("sources", "archive", month, name))


def _claim_set_json(root: Path) -> str:
    """Build the claim-set string the prompt carries (reuses export-claims)."""
    from klyreon.commands.export_claims import CommandExportClaims

    result = CommandExportClaims(root).execute()
    return result.output or json.dumps({"claims": []})


def ingest_source(  # noqa: PLR0913 - the per-source loop's inputs; all required
    root: Path,
    source_rel: str,
    *,
    backend: Backend,
    identity: GitIdentity,
    now: dt.datetime,
    run_id: str,
    timeout: int,
    max_body_lines: int = 60,
    dry_run: bool = False,
    claim_set: str | None = None,
) -> SourceOutcome:
    """Ingest one source document. Returns its outcome; never raises for a
    per-source failure (the sweep continues) — only programmer errors escape.
    """
    source_name = Path(source_rel).stem
    outcome = SourceOutcome(source=source_rel, status=SourceStatus.FAILED)

    try:
        source_doc = parse_file(root / source_rel, FileKind.SOURCE)
    except (FrontmatterError, OSError) as exc:
        outcome.error = f"cannot read source {source_rel}: {exc}"
        return outcome

    archive_rel = _archive_path_for(source_rel)
    voice, voice_warning = load_voice(root)
    if voice_warning:
        outcome.warnings.append(voice_warning)

    prompt = assemble_prompt(
        source_text=source_doc.body,
        source_archive_path=archive_rel,
        claim_set=claim_set if claim_set is not None else _claim_set_json(root),
        voice=voice,
        max_body_lines=max_body_lines,
    )

    try:
        payload: IngestPayload = backend.run(prompt, timeout)
    except BackendError as exc:
        outcome.error = f"backend failed ({exc.reason.value}): {exc.detail}"
        return outcome

    try:
        rendered = render_zettels(
            payload,
            source_archive_path=archive_rel,
            notes_dir=root / "wiki" / "notes",
            now=now,
            max_body_lines=max_body_lines,
        )
    except RenderError as exc:
        outcome.error = str(exc)
        return outcome

    conflict_outcome = apply_conflicts(payload, rendered, root=root, now=now)
    corroboration_lines = apply_corroborations(payload, rendered)

    # Author MOCs for every moc path the rendered zettels name.
    moc_docs = _author_mocs(root, rendered, now=now)

    outcome.zettels_created = [r.rel_path for r in rendered]
    outcome.conflict_lines = conflict_outcome.trail_lines
    outcome.corroboration_lines = corroboration_lines
    outcome.mocs_touched = [rel for rel, _ in moc_docs]

    if dry_run:
        outcome.status = SourceStatus.DRY_RUN
        return outcome

    sha = _stage_and_apply(
        root,
        source_rel=source_rel,
        archive_rel=archive_rel,
        rendered=rendered,
        edits=conflict_outcome.edits,
        moc_docs=moc_docs,
        identity=identity,
        run_id=run_id,
        source_name=source_name,
        outcome=outcome,
    )
    if sha is not None:
        outcome.status = SourceStatus.COMMITTED
        outcome.commit_sha = sha
    return outcome


def _author_mocs(root: Path, rendered: list[RenderedZettel], now: dt.datetime) -> list[tuple[str, Document]]:
    members_by_moc: dict[str, list[str]] = {}
    for r in rendered:
        for moc_rel in r.document.get("mocs") or []:
            members_by_moc.setdefault(moc_rel, []).append(r.rel_path)
    docs: list[tuple[str, Document]] = []
    for moc_rel, members in members_by_moc.items():
        docs.append((moc_rel, ensure_moc(root, moc_rel, members, now=now)))
    return docs


def _stage_and_apply(  # noqa: PLR0913 - one cohesive apply step; args are the staged set
    root: Path,
    *,
    source_rel: str,
    archive_rel: str,
    rendered: list[RenderedZettel],
    edits: list[EditedZettel],
    moc_docs: list[tuple[str, Document]],
    identity: GitIdentity,
    run_id: str,
    source_name: str,
    outcome: SourceOutcome,
) -> str | None:
    staging = Staging(run_id=run_id, source=source_name)
    for r in rendered:
        staging.stage(r.rel_path, serialize(r.document))
    for edit in edits:
        staging.stage(edit.rel_path, serialize(edit.document))
    for moc_rel, moc_doc in moc_docs:
        staging.stage(moc_rel, serialize(moc_doc))
    staging.stage_source_move(source_rel, archive_rel)

    subject = f"ingest: {source_name}"
    try:
        return staging.apply(root, identity, subject)
    except StagingError as exc:
        outcome.error = str(exc)
        return None


def _inbox_sources(root: Path) -> list[str]:
    """Vault-relative source paths in the inbox, filename order, archive excluded."""
    sources_dir = root / "sources"
    if not sources_dir.is_dir():
        return []
    found: list[str] = []
    for md in sources_dir.rglob("*.md"):
        rel = md.relative_to(root)
        if rel.parts[:2] == ("sources", "archive"):
            continue
        found.append(rel.as_posix())
    return sorted(found, key=lambda p: Path(p).name)


def sweep_sources(  # noqa: PLR0913 - run-bound knobs; all configured, all required
    root: Path,
    *,
    backend: Backend,
    identity: GitIdentity,
    now: dt.datetime,
    max_sources: int = 5,
    timeout: int = 900,
    max_body_lines: int = 60,
    dry_run: bool = False,
    only: str | None = None,
) -> SweepResult:
    """Sweep the inbox (or a single source) under the run bounds.

    Args:
        only: Vault-relative path of a single source to ingest; when ``None``
            the whole inbox is swept.
    """
    result = SweepResult()
    run_id = now.strftime("%Y%m%d%H%M%S")

    if only is not None:
        selected = [only]
    else:
        all_sources = _inbox_sources(root)
        selected = all_sources[:max_sources]
        result.deferred = all_sources[max_sources:]

    claim_set = _claim_set_json(root)

    for idx, source_rel in enumerate(selected):
        source_now = now + dt.timedelta(seconds=idx * 10)
        outcome = ingest_source(
            root,
            source_rel,
            backend=backend,
            identity=identity,
            now=source_now,
            run_id=run_id,
            timeout=timeout,
            max_body_lines=max_body_lines,
            dry_run=dry_run,
            claim_set=claim_set,
        )
        if outcome.status is SourceStatus.DRY_RUN:
            result.dry_run.append(outcome)
        elif outcome.status is SourceStatus.COMMITTED:
            result.committed.append(outcome)
        else:
            result.failed.append(outcome)

    return result

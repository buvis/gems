"""The maintenance sweep: the whole pass over the vault, orchestrated.

Order (PRD "maintain command"): lint the whole vault (reuse PRD A's
``validate_vault``, never fix), apply lifecycle + assent transitions (one commit
per zettel), reconcile MOC membership (one commit per MOC), detect prune
candidates (delete only when enabled, one grouped commit per prune), then write
and commit the trail. ``last_maintain`` is stamped into state at the end.

Idempotent by construction: every rule is a function of vault state, so a
second run plans nothing and writes only its trail. ``--dry-run`` reports every
transition and candidate and writes NOTHING — not even the trail.

No LLM call anywhere: every rule is deterministic.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from klyreon.maintain.graph import VaultGraph
from klyreon.maintain.moc_sync import apply_moc_sync, plan_moc_sync
from klyreon.maintain.prune import PruneCandidate, find_candidates, prune
from klyreon.maintain.rules import Transition, plan_assent, plan_lifecycle
from klyreon.spec.model import Document
from klyreon.spec.validator import SpecError, validate_vault
from klyreon.spec.writer import write_document
from klyreon.vault.git import GitIdentity, commit
from klyreon.vault.state import read_state, write_state

__all__ = ["MaintainResult", "run_maintain"]


@dataclass(slots=True)
class MaintainResult:
    """Everything one maintenance sweep did (or would do, under dry-run)."""

    dry_run: bool = False
    lint_findings: list[SpecError] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    moc_reconciled: list[str] = field(default_factory=list)
    prune_candidates: list[PruneCandidate] = field(default_factory=list)
    pruned: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)
    trail: str | None = None

    @property
    def lint_errors(self) -> int:
        return len(self.lint_findings)


def _apply_transition(root: Path, zettel: Document, transition: Transition, identity: GitIdentity) -> str:
    """Write the single-field change and commit the zettel on its own."""
    zettel.frontmatter[transition.field] = transition.new
    write_document(zettel, root / zettel.path)
    from pathlib import PurePosixPath

    stem = PurePosixPath(zettel.path).stem
    subject = f"maintain: {zettel.path} {transition.field} {transition.old} to {transition.new} ({stem})"
    return commit(root, [zettel.path], subject, identity)


def run_maintain(  # noqa: PLR0913 - the ordered sweep; each block is one PRD step
    root: Path,
    *,
    identity: GitIdentity,
    now: dt.datetime,
    max_body_lines: int = 60,
    prune_window_days: int = 365,
    pruning_enabled: bool = False,
    dry_run: bool = False,
    write_state_on_finish: bool = True,
) -> MaintainResult:
    """Run one maintenance sweep over the vault at ``root``.

    The caller (``CommandMaintain``) owns the autonomy gate and the lock; this
    function assumes it holds both. Returns a :class:`MaintainResult`.
    """
    result = MaintainResult(dry_run=dry_run)

    # 1. Lint — reported, never fixed. Does not block the transitions below.
    result.lint_findings = validate_vault(root, max_body_lines=max_body_lines)

    # 2. Transitions. Build the graph once, plan every change, apply per zettel.
    graph = VaultGraph.build(root)
    planned: list[Transition] = []
    for path in sorted(graph.zettels):
        zettel = graph.zettels[path]
        for planner in (plan_lifecycle, plan_assent):
            transition = planner(zettel, graph)
            if transition is not None:
                planned.append(transition)
    result.transitions = planned

    if not dry_run:
        for transition in planned:
            zettel = graph.zettels[transition.path]
            sha = _apply_transition(root, zettel, transition, identity)
            result.commits.append(sha)

    # 3. MOC membership reconciliation (rebuild graph if transitions changed disk).
    sync_graph = VaultGraph.build(root) if (planned and not dry_run) else graph
    moc_plan = plan_moc_sync(sync_graph)
    result.moc_reconciled = [d.moc_path for d in moc_plan.drifts]
    if not dry_run and not moc_plan.is_empty:
        applied = apply_moc_sync(root, sync_graph, moc_plan, identity=identity, now=now)
        result.commits.extend(sha for _, sha in applied)

    # 4. Prune detection (always) and opt-in deletion.
    prune_graph = VaultGraph.build(root) if (not dry_run and (planned or not moc_plan.is_empty)) else sync_graph
    candidates = find_candidates(prune_graph, window_days=prune_window_days, now=now)
    result.prune_candidates = candidates
    if pruning_enabled and not dry_run:
        for candidate in candidates:
            sha = prune(root, candidate, prune_graph, identity=identity)
            result.pruned.append(candidate.path)
            result.commits.append(sha)

    # 5. Trail + last_maintain (never under dry-run).
    if not dry_run:
        result.trail = _write_trail(root, result, identity=identity, now=now)
        if write_state_on_finish:
            state = read_state()
            state["last_maintain"] = now.isoformat()
            write_state(state)

    return result


def _section(title: str, lines: list[str]) -> list[str]:
    if not lines:
        return [f"## {title}", "", "_none_", ""]
    return [f"## {title}", "", *[f"- {ln}" for ln in lines], ""]


def _write_trail(root: Path, result: MaintainResult, *, identity: GitIdentity, now: dt.datetime) -> str:
    """Write and commit the maintain trail; return its vault-relative path."""
    from buvis.pybase.filesystem import atomic_write_text

    from klyreon.spec.enums import AuxKind
    from klyreon.spec.model import FileKind
    from klyreon.spec.writer import serialize

    trail_id = now.strftime("%Y%m%d%H%M%S")
    title = f"Maintain run {now.date().isoformat()}"
    front: dict[str, object] = {
        "id": trail_id,
        "title": title,
        "created": now.isoformat(),
        "kind": AuxKind.TRAIL.value,
    }
    body_lines: list[str] = [f"# {title}", "", "run: maintain", ""]
    body_lines += _section("Lint findings", [f"{e.path}: [{e.rule}] {e.message}" for e in result.lint_findings])
    body_lines += _section(
        "Transitions",
        [f"{t.path}: {t.field} {t.old} -> {t.new} ({t.reason})" for t in result.transitions],
    )
    body_lines += _section("MOCs reconciled", result.moc_reconciled)
    body_lines += _section(
        "Prune candidates",
        [f"{c.path}: {c.reason}" for c in result.prune_candidates],
    )
    body_lines += _section("Pruned", result.pruned)
    body = "\n" + "\n".join(body_lines).rstrip("\n") + "\n"

    doc = Document(path=f"wiki/trails/{trail_id}.md", kind=FileKind.AUX, frontmatter=front, body=body, h1=title)
    trail_abs = root / doc.path
    trail_abs.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(trail_abs, serialize(doc))
    commit(root, [doc.path], f"maintain: run journal {trail_id}", identity)
    return doc.path

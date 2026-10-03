"""Reconcile every MOC's member block with the zettels that anchor to it.

Membership is a function of the vault, not an append log: a zettel whose
``mocs`` names a MOC must appear in that MOC's ``<!-- klyreon:members -->``
block, and a listed member whose zettel no longer names the MOC (or no longer
exists) must disappear from it. Only the marked block is rewritten, so human
prose around it survives — the rule PRD B's :func:`ensure_moc` established and
this module reuses by rewriting through the same block regex.

Pure planning (:func:`plan_moc_sync`) is separated from the committing apply
(:func:`apply_moc_sync`) so the sweep can report a dry run without writing, and
so a second sweep over a reconciled vault plans nothing. One commit per MOC
that drifted keeps every change auditable. A MOC named by a zettel but absent
from disk is NOT created here — that is a lint finding; maintain never authors
MOCs.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from klyreon.ingest.moc import _BLOCK_RE, MEMBERS_CLOSE, MEMBERS_OPEN
from klyreon.maintain.graph import VaultGraph
from klyreon.spec.model import Document, FileKind
from klyreon.spec.writer import serialize
from klyreon.vault.git import GitIdentity, commit

__all__ = ["MocDrift", "MocSyncPlan", "apply_moc_sync", "plan_moc_sync"]


@dataclass(frozen=True, slots=True)
class MocDrift:
    """One MOC whose member block does not match the graph.

    Attributes:
        moc_path: The MOC's vault-relative path.
        desired: The member zettel paths that SHOULD be listed, sorted.
        added: Members present in ``desired`` but missing from the block.
        removed: Members in the block that are no longer anchored (or gone).
    """

    moc_path: str
    desired: tuple[str, ...]
    added: tuple[str, ...]
    removed: tuple[str, ...]


@dataclass(slots=True)
class MocSyncPlan:
    """Every MOC that drifted. Empty :attr:`drifts` means nothing to do."""

    drifts: list[MocDrift] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.drifts


def _member_link(member_rel_path: str) -> str:
    stem = PurePosixPath(member_rel_path).stem
    return f"- [{stem}]({member_rel_path})"


def _render_block(member_links: list[str]) -> str:
    inner = "\n".join(member_links)
    middle = f"\n{inner}\n" if inner else "\n"
    return f"{MEMBERS_OPEN}{middle}{MEMBERS_CLOSE}"


def _listed_members(block_body: str) -> list[str]:
    """Extract the vault-relative member paths from a rendered block body."""
    members: list[str] = []
    for line in block_body.splitlines():
        text = line.strip()
        if not text:
            continue
        # Lines look like ``- [stem](wiki/notes/<id>.md)``; take the path.
        start = text.rfind("(")
        end = text.rfind(")")
        if start != -1 and end != -1 and end > start:
            members.append(text[start + 1 : end])
    return members


def _desired_members(graph: VaultGraph, moc_path: str) -> list[str]:
    """The zettels whose ``mocs`` names ``moc_path``, sorted by path."""
    desired: list[str] = []
    for rel, doc in graph.zettels.items():
        for moc_rel in doc.get("mocs") or []:
            if isinstance(moc_rel, str) and moc_rel == moc_path:
                desired.append(rel)
                break
    return sorted(desired)


def plan_moc_sync(graph: VaultGraph) -> MocSyncPlan:
    """Return the per-MOC additions and removals; empty when nothing drifted."""
    plan = MocSyncPlan()
    for moc_path, moc_doc in sorted(graph.mocs.items()):
        desired = _desired_members(graph, moc_path)
        match = _BLOCK_RE.search(moc_doc.body)
        current = _listed_members(match.group("members")) if match is not None else []

        desired_set = set(desired)
        current_set = set(current)
        added = sorted(desired_set - current_set)
        removed = sorted(current_set - desired_set)
        if added or removed:
            plan.drifts.append(
                MocDrift(
                    moc_path=moc_path,
                    desired=tuple(desired),
                    added=tuple(added),
                    removed=tuple(removed),
                ),
            )
    return plan


def _reconciled_document(moc_doc: Document, drift: MocDrift) -> Document:
    """Return a copy of ``moc_doc`` with its member block rewritten to ``desired``."""
    links = [_member_link(m) for m in drift.desired]
    block = _render_block(links)
    match = _BLOCK_RE.search(moc_doc.body)
    if match is None:
        new_body = moc_doc.body.rstrip("\n") + f"\n\n{block}\n"
    else:
        new_body = moc_doc.body[: match.start()] + block + moc_doc.body[match.end() :]
    return Document(
        path=moc_doc.path,
        kind=FileKind.AUX,
        frontmatter=moc_doc.frontmatter,
        body=new_body,
        h1=moc_doc.h1,
    )


def apply_moc_sync(
    root: Path,
    graph: VaultGraph,
    plan: MocSyncPlan,
    *,
    identity: GitIdentity,
    now: dt.datetime,  # noqa: ARG001 - kept for signature symmetry with other appliers
) -> list[tuple[str, str]]:
    """Rewrite each drifted MOC's member block and commit, one commit per MOC.

    Returns ``[(moc_path, commit_sha), ...]`` in plan order. Only the marked
    block is rewritten, so human prose around it is preserved verbatim.
    """
    from buvis.pybase.filesystem import atomic_write_text

    applied: list[tuple[str, str]] = []
    for drift in plan.drifts:
        moc_doc = graph.mocs[drift.moc_path]
        reconciled = _reconciled_document(moc_doc, drift)
        abs_path = root / drift.moc_path
        atomic_write_text(abs_path, serialize(reconciled))
        sha = commit(root, [drift.moc_path], f"maintain: reconcile MOC {PurePosixPath(drift.moc_path).stem}", identity)
        applied.append((drift.moc_path, sha))
    return applied

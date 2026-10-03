"""Prune-candidate detection and the grouped delete-plus-cleanup.

Detection always runs; deletion happens only when ``pruning_enabled`` (the
caller passes it). A candidate is ``lifecycle: fleeting``, with no inbound and
no outbound links, no corroboration, ``assent`` other than ``rejected``, an
empty ``delivered-as``, and an ``updated`` (or ``created`` when absent) older
than the window. The two exemptions are spec 7.3's: a ``rejected`` zettel is
the record of what was considered and refused, and a ``delivered-as`` zettel
backs work that already shipped.

:func:`prune` removes a candidate AND every inbound reference to it — each
inbound ``links`` entry, every ``doubts[].target`` naming it, and its MOC
membership — in ONE commit, so no sweep ever leaves a dangling reference. Each
cleaned file and the deletion go into the same scoped commit; the re-run picks
up the remaining candidates.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from klyreon.ingest.moc import _BLOCK_RE, MEMBERS_CLOSE, MEMBERS_OPEN
from klyreon.maintain.graph import VaultGraph
from klyreon.spec.enums import Assent, Lifecycle
from klyreon.spec.model import Document
from klyreon.spec.writer import serialize
from klyreon.vault.git import GitIdentity, _run_git

__all__ = ["PruneCandidate", "find_candidates", "prune"]


@dataclass(frozen=True, slots=True)
class PruneCandidate:
    """One zettel that never earned survival.

    Attributes:
        path: The candidate zettel's vault-relative path.
        reason: Why it qualified (for the trail and ``status``).
    """

    path: str
    reason: str


def _parse_iso(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _age_anchor(doc: Document) -> dt.datetime | None:
    """The timestamp a candidate's age is measured from: ``updated`` else ``created``."""
    return _parse_iso(doc.get("updated")) or _parse_iso(doc.get("created"))


def find_candidates(graph: VaultGraph, *, window_days: int, now: dt.datetime) -> list[PruneCandidate]:
    """Return the prune candidates, sorted by path. Detection always runs."""
    window = dt.timedelta(days=window_days)
    candidates: list[PruneCandidate] = []

    for path, doc in sorted(graph.zettels.items()):
        if doc.get("lifecycle") != Lifecycle.FLEETING.value:
            continue
        if doc.get("assent") == Assent.REJECTED.value:
            continue  # the record of what was refused
        if doc.get("delivered-as"):
            continue  # backs work that already shipped
        if graph.outbound_count(path) > 0 or graph.inbound(path):
            continue
        if graph.corroborating_sources(path, include_own=True):
            continue
        anchor = _age_anchor(doc)
        if anchor is None:
            continue
        if now - anchor <= window:
            continue
        age_days = (now - anchor).days
        candidates.append(
            PruneCandidate(
                path=path,
                reason=f"fleeting, unlinked, uncorroborated, idle {age_days}d (window {window_days}d)",
            ),
        )
    return candidates


def _strip_inbound_links(doc: Document, target: str) -> bool:
    """Drop every ``links`` entry pointing at ``target``. Return True if changed."""
    links = doc.get("links")
    if not isinstance(links, list):
        return False
    kept = [link for link in links if not (isinstance(link, dict) and link.get("to") == target)]
    if len(kept) == len(links):
        return False
    if kept:
        doc.frontmatter["links"] = kept
    else:
        doc.frontmatter.pop("links", None)
    return True


def _strip_doubt_targets(doc: Document, target: str) -> bool:
    """Drop ``target`` from any ``doubts[].target`` naming it. Return True if changed."""
    doubts = doc.get("doubts")
    if not isinstance(doubts, list):
        return False
    changed = False
    for doubt in doubts:
        if not isinstance(doubt, dict):
            continue
        dtarget = doubt.get("target")
        if isinstance(dtarget, dict) and dtarget.get("to") == target:
            doubt.pop("target", None)
            changed = True
    return changed


def _strip_moc_member(moc_doc: Document, target: str) -> bool:
    """Remove ``target`` from a MOC's member block. Return True if changed."""
    match = _BLOCK_RE.search(moc_doc.body)
    if match is None:
        return False
    kept_lines: list[str] = []
    changed = False
    for line in match.group("members").splitlines():
        text = line.strip()
        if not text:
            continue
        if f"({target})" in text:
            changed = True
            continue
        kept_lines.append(text)
    if not changed:
        return False
    inner = "\n".join(kept_lines)
    middle = f"\n{inner}\n" if inner else "\n"
    block = f"{MEMBERS_OPEN}{middle}{MEMBERS_CLOSE}"
    moc_doc.body = moc_doc.body[: match.start()] + block + moc_doc.body[match.end() :]
    return True


def prune(
    root: Path,
    candidate: PruneCandidate,
    graph: VaultGraph,
    *,
    identity: GitIdentity,
) -> str:
    """Delete ``candidate`` and clean every inbound reference, in one commit.

    Rewrites every zettel that linked to it or doubted it, every MOC that
    listed it, deletes the file, and commits exactly those paths together.

    Returns the commit SHA.
    """
    from buvis.pybase.filesystem import atomic_write_text

    target = candidate.path
    changed_paths: list[str] = []

    for rel, doc in graph.zettels.items():
        if rel == target:
            continue
        links_changed = _strip_inbound_links(doc, target)
        doubts_changed = _strip_doubt_targets(doc, target)
        if links_changed or doubts_changed:
            atomic_write_text(root / rel, serialize(doc))
            changed_paths.append(rel)

    for rel, moc_doc in graph.mocs.items():
        if _strip_moc_member(moc_doc, target):
            atomic_write_text(root / rel, serialize(moc_doc))
            changed_paths.append(rel)

    (root / target).unlink()

    # Stage the deletion plus every cleaned inbound reference in one commit so an
    # interrupted sweep never leaves a dangling reference.
    stem = PurePosixPath(target).stem
    _run_git(root, ["add", "--", target, *changed_paths])
    _run_git(
        root,
        [
            "-c",
            f"user.name={identity.name}",
            "-c",
            f"user.email={identity.email}",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            f"maintain: prune {stem}",
            "--",
            target,
            *changed_paths,
        ],
    )
    return _run_git(root, ["rev-parse", "HEAD"]).stdout.strip()

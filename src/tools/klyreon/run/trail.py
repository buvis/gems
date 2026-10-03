"""The run journal: every ingest run writes one trail file.

``wiki/trails/YYYYMMDDHHmmSS.md`` with ``kind: trail`` (spec 3.3), written and
committed at the end of the run as its own commit (PRD "Trail file per run").
Per-source atomicity covers each source's own writes, so the two rules do not
collide: a run that dies before writing the trail leaves the per-source commits
as the record.

Sections: sources committed, sources failed with the reason, sources deferred
by the cap, zettels created, each conflict and the shape it resolved into,
corroborations, MOCs touched. 3.3 fixes only the frontmatter contract, so these
sections can grow without a spec edit.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from klyreon.ingest.pipeline import SweepResult
from klyreon.spec.enums import AuxKind
from klyreon.spec.model import Document, FileKind
from klyreon.spec.writer import serialize
from klyreon.vault.git import GitIdentity, commit

__all__ = ["build_trail_document", "write_trail"]


def _section(title: str, lines: list[str]) -> list[str]:
    if not lines:
        return [f"## {title}", "", "_none_", ""]
    return [f"## {title}", "", *[f"- {ln}" for ln in lines], ""]


def build_trail_document(result: SweepResult, *, now: dt.datetime, run: str = "ingest") -> Document:
    """Build the trail :class:`Document` for one run (not yet written)."""
    trail_id = now.strftime("%Y%m%d%H%M%S")
    title = f"Ingest run {now.date().isoformat()}"
    front: dict[str, object] = {
        "id": trail_id,
        "title": title,
        "created": now.isoformat(),
        "kind": AuxKind.TRAIL.value,
    }

    committed = [f"{o.source} -> {o.commit_sha or '?'}" for o in result.committed]
    failed = [f"{o.source}: {o.error or 'unknown error'}" for o in result.failed]
    zettels: list[str] = [z for o in result.committed for z in o.zettels_created]
    conflicts: list[str] = [c for o in result.committed for c in o.conflict_lines]
    corroborations: list[str] = [c for o in result.committed for c in o.corroboration_lines]
    mocs: list[str] = sorted({m for o in result.committed for m in o.mocs_touched})

    body_lines: list[str] = [f"# {title}", "", f"run: {run}", ""]
    body_lines += _section("Sources committed", committed)
    body_lines += _section("Sources failed", failed)
    body_lines += _section("Sources deferred", result.deferred)
    body_lines += _section("Zettels created", zettels)
    body_lines += _section("Conflicts", conflicts)
    body_lines += _section("Corroborations", corroborations)
    body_lines += _section("MOCs touched", mocs)
    body = "\n" + "\n".join(body_lines).rstrip("\n") + "\n"

    return Document(path=f"wiki/trails/{trail_id}.md", kind=FileKind.AUX, frontmatter=front, body=body, h1=title)


def write_trail(
    root: Path,
    result: SweepResult,
    *,
    identity: GitIdentity,
    now: dt.datetime,
    run: str = "ingest",
) -> tuple[str, str]:
    """Write the trail and commit it as its own commit.

    Returns ``(trail_rel_path, commit_sha)``.
    """
    doc = build_trail_document(result, now=now, run=run)
    trail_abs = root / doc.path
    trail_abs.parent.mkdir(parents=True, exist_ok=True)
    from buvis.pybase.filesystem import atomic_write_text

    atomic_write_text(trail_abs, serialize(doc))
    sha = commit(root, [doc.path], f"ingest: run journal {doc.frontmatter['id']}", identity)
    return doc.path, sha

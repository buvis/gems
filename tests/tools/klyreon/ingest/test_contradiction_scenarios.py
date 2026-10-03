"""Phase 2: contradiction scenarios end to end (discovery criterion 2)."""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pytest
from klyreon.backends.stub import StubBackend
from klyreon.commands.ingest import CommandIngest
from klyreon.spec.model import FileKind
from klyreon.spec.parser import parse_file
from klyreon.spec.validator import validate_vault

from .conftest import CONFLICT_SOURCES, load_payloads

pytestmark = pytest.mark.klyreon

NOW = dt.datetime(2026, 5, 11, 9, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))


def _seed_conflict_sources(vault: Path, names: list[str]) -> None:
    dest = vault / "sources" / "2026-05"
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(CONFLICT_SOURCES / f"{name}.md", dest / f"{name}.md")


def _links_of(vault: Path, zettel_rel: str, rel: str) -> list[str]:
    doc = parse_file(vault / zettel_rel, FileKind.ZETTEL)
    return [e["to"] for e in (doc.get("links") or []) if e.get("rel") == rel]


class TestEachShapeResolves:
    def test_five_conflicts_resolve_to_their_shapes(self, git_conflict_vault: Path) -> None:
        _seed_conflict_sources(
            git_conflict_vault,
            [
                "conflict-aporia-doubt",
                "conflict-refine",
                "conflict-supersede",
                "conflict-rejected-target",
                "conflict-aporia-zettel",
            ],
        )
        stub = StubBackend(by_marker=load_payloads().CONFLICTS)
        result = CommandIngest(git_conflict_vault, backend=stub, max_sources=10, now=NOW).execute()
        assert result.success, result.error
        assert result.metadata["committed"] == 5
        assert not validate_vault(git_conflict_vault)

        accepted = "wiki/notes/20260301090000.md"
        rejected = "wiki/notes/20260301093000.md"
        accepted_doc = parse_file(git_conflict_vault / accepted, FileKind.ZETTEL)
        # The accepted baseline gained a contradicts link (from the aporia).
        assert any(e.get("rel") == "contradicts" for e in (accepted_doc.get("links") or []))
        # Supersede moved the accepted baseline to rejected.
        assert accepted_doc.get("assent") == "rejected"
        # The rejected baseline was never edited by the rejected-target conflict.
        rejected_doc = parse_file(git_conflict_vault / rejected, FileKind.ZETTEL)
        assert rejected_doc.get("assent") == "rejected"


class TestThreeConsecutiveRunsStable:
    def test_same_shapes_three_times(self, git_conflict_vault: Path) -> None:
        shapes_each_run: list[set[str]] = []
        for run_idx in range(3):
            _seed_conflict_sources(git_conflict_vault, ["conflict-aporia-doubt", "conflict-refine"])
            now = NOW + dt.timedelta(hours=run_idx)
            stub = StubBackend(by_marker=load_payloads().CONFLICTS)
            result = CommandIngest(git_conflict_vault, backend=stub, max_sources=10, now=now).execute()
            assert result.success, result.error
            # Collect the conflict shapes recorded in this run's trail.
            trail = sorted((git_conflict_vault / "wiki" / "trails").glob("*.md"))[-1]
            text = trail.read_text()
            shapes = set()
            if "APORIA" in text:
                shapes.add("aporia")
            if "REFINE" in text:
                shapes.add("refine")
            shapes_each_run.append(shapes)
        # All three runs produced the same shape set.
        assert shapes_each_run[0] == shapes_each_run[1] == shapes_each_run[2] == {"aporia", "refine"}
        assert not validate_vault(git_conflict_vault)


class TestSharedMissingMoc:
    def test_two_zettels_one_missing_moc_created_once(self, git_conflict_vault: Path) -> None:
        # The aporia-zettel source yields two zettels, both anchoring epistemics
        # (which exists). Use a source whose payload anchors a *missing* MOC.
        from klyreon.backends.base import IngestPayload, PayloadClaim, ZettelDraft

        missing_moc = "wiki/mocs/brand-new.md"
        payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="A",
                    concept_type="observation",
                    claims=[PayloadClaim(id="c1", statement="a")],
                    mocs=[missing_moc],
                ),
                ZettelDraft(
                    title="B",
                    concept_type="observation",
                    claims=[PayloadClaim(id="c1", statement="b")],
                    mocs=[missing_moc],
                ),
            ],
        )
        (git_conflict_vault / "sources" / "2026-05").mkdir(parents=True, exist_ok=True)
        multi_content = (
            "---\nid: multi\ntitle: Multi\n"
            "created: 2026-05-01T09:00:00+02:00\ntype: article\n---\n\n"
            "# Multi\n\n<!-- stub-marker: multi -->\nbody\n"
        )
        (git_conflict_vault / "sources" / "2026-05" / "multi.md").write_text(multi_content, encoding="utf-8")
        stub = StubBackend(by_marker={"multi": payload})
        result = CommandIngest(git_conflict_vault, backend=stub, now=NOW).execute()
        assert result.success, result.error
        moc = git_conflict_vault / missing_moc
        assert moc.is_file()
        # Both members listed once, in a single created MOC.
        body = moc.read_text()
        assert body.count("](wiki/notes/") == 2
        assert not validate_vault(git_conflict_vault)

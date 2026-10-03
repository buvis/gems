"""Phase 0: the derived VaultGraph views."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.maintain.graph import VaultGraph

from tests.tools.klyreon.maintain.conftest import make_vault, write_moc, write_source, write_zettel

pytestmark = pytest.mark.klyreon


class TestInbound:
    def test_inbound_records_source_and_relation(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_zettel(root, "20260101000001", lifecycle="literature")
        write_zettel(
            root,
            "20260101000002",
            links=[{"rel": "supports", "to": "wiki/notes/20260101000001.md"}],
        )
        graph = VaultGraph.build(root)
        inbound = graph.inbound("wiki/notes/20260101000001.md")
        assert len(inbound) == 1
        assert inbound[0].source == "wiki/notes/20260101000002.md"
        assert inbound[0].rel == "supports"

    def test_no_inbound_is_empty(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_zettel(root, "20260101000001")
        graph = VaultGraph.build(root)
        assert graph.inbound("wiki/notes/20260101000001.md") == []


class TestCorroboratingSources:
    def test_counts_across_supporters_excluding_own(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        write_source(root, "sources/archive/2026-04/b.md")
        target = write_zettel(
            root,
            "20260101000001",
            sources=["sources/archive/2026-04/a.md"],
        )
        write_zettel(
            root,
            "20260101000002",
            sources=["sources/archive/2026-04/b.md"],
            links=[{"rel": "supports", "to": target}],
        )
        graph = VaultGraph.build(root)
        # Excluding own: only the supporter's distinct source counts.
        corroborating = graph.corroborating_sources(target, include_own=False)
        assert corroborating == {"sources/archive/2026-04/b.md"}
        # Including own: both.
        both = graph.corroborating_sources(target, include_own=True)
        assert both == {"sources/archive/2026-04/a.md", "sources/archive/2026-04/b.md"}

    def test_two_supporters_same_source_is_one_distinct(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        target = write_zettel(root, "20260101000001")
        for zid in ("20260101000002", "20260101000003"):
            write_zettel(
                root,
                zid,
                sources=["sources/archive/2026-04/a.md"],
                links=[{"rel": "supports", "to": target}],
            )
        graph = VaultGraph.build(root)
        assert graph.corroborating_sources(target, include_own=False) == {"sources/archive/2026-04/a.md"}


class TestOpenDisagreements:
    def test_disagreement_targeting_X_from_Y_counts_against_X(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        x = write_zettel(root, "20260101000001")
        write_zettel(
            root,
            "20260101000002",
            doubts=[
                {
                    "mode": "disagreement",
                    "claim": "c1",
                    "rationale": "I disagree with X",
                    "target": {"to": x, "claim": "c1"},
                },
            ],
        )
        graph = VaultGraph.build(root)
        # The doubt lives in Y but names X: it holds X, not Y.
        assert graph.open_disagreements(x) is True

    def test_self_disagreement_counts(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        z = write_zettel(
            root,
            "20260101000001",
            doubts=[{"mode": "disagreement", "claim": "c1", "rationale": "self-doubt"}],
        )
        graph = VaultGraph.build(root)
        assert graph.open_disagreements(z) is True

    def test_no_disagreement_is_false(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        z = write_zettel(root, "20260101000001")
        graph = VaultGraph.build(root)
        assert graph.open_disagreements(z) is False


class TestMocsLoaded:
    def test_mocs_are_indexed(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_moc(root, "architecture", [])
        graph = VaultGraph.build(root)
        assert "wiki/mocs/architecture.md" in graph.mocs

"""Phase 1: the lifecycle and assent transition planners."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.maintain.graph import VaultGraph
from klyreon.maintain.rules import plan_assent, plan_lifecycle

from tests.tools.klyreon.maintain.conftest import make_vault, write_source, write_zettel

pytestmark = pytest.mark.klyreon


class TestLifecycle:
    def test_fleeting_to_literature_when_sourced_and_linked(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        other = write_zettel(root, "20260101000002", lifecycle="literature")
        z = write_zettel(
            root,
            "20260101000001",
            lifecycle="fleeting",
            sources=["sources/archive/2026-04/a.md"],
            links=[{"rel": "supports", "to": other}],
        )
        graph = VaultGraph.build(root)
        t = plan_lifecycle(graph.zettels[z], graph)
        assert t is not None
        assert (t.old, t.new, t.field) == ("fleeting", "literature", "lifecycle")

    def test_fleeting_stays_without_source(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        other = write_zettel(root, "20260101000002", lifecycle="literature")
        z = write_zettel(
            root,
            "20260101000001",
            lifecycle="fleeting",
            links=[{"rel": "supports", "to": other}],
        )
        graph = VaultGraph.build(root)
        assert plan_lifecycle(graph.zettels[z], graph) is None

    def test_fleeting_stays_without_link(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        z = write_zettel(root, "20260101000001", lifecycle="fleeting", sources=["sources/archive/2026-04/a.md"])
        graph = VaultGraph.build(root)
        assert plan_lifecycle(graph.zettels[z], graph) is None

    def test_literature_to_evergreen_with_two_distinct_sources(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        write_source(root, "sources/archive/2026-04/b.md")
        z = write_zettel(
            root,
            "20260101000001",
            lifecycle="literature",
            sources=["sources/archive/2026-04/a.md", "sources/archive/2026-04/b.md"],
        )
        graph = VaultGraph.build(root)
        t = plan_lifecycle(graph.zettels[z], graph)
        assert t is not None
        assert (t.old, t.new) == ("literature", "evergreen")

    def test_literature_stays_with_one_source(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        z = write_zettel(root, "20260101000001", lifecycle="literature", sources=["sources/archive/2026-04/a.md"])
        graph = VaultGraph.build(root)
        assert plan_lifecycle(graph.zettels[z], graph) is None

    def test_promotion_does_not_touch_processed(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        other = write_zettel(root, "20260101000002", lifecycle="literature")
        z = write_zettel(
            root,
            "20260101000001",
            lifecycle="fleeting",
            processed=True,
            sources=["sources/archive/2026-04/a.md"],
            links=[{"rel": "supports", "to": other}],
        )
        graph = VaultGraph.build(root)
        t = plan_lifecycle(graph.zettels[z], graph)
        # The planner only names the lifecycle field; processed is never in a transition.
        assert t is not None
        assert t.field == "lifecycle"


class TestAssent:
    def test_tentative_to_accepted_with_two_corroborations(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/b.md")
        write_source(root, "sources/archive/2026-04/c.md")
        target = write_zettel(root, "20260101000001", assent="tentative")
        write_zettel(
            root,
            "20260101000002",
            sources=["sources/archive/2026-04/b.md"],
            links=[{"rel": "supports", "to": target}],
        )
        write_zettel(
            root,
            "20260101000003",
            sources=["sources/archive/2026-04/c.md"],
            links=[{"rel": "supports", "to": target}],
        )
        graph = VaultGraph.build(root)
        t = plan_assent(graph.zettels[target], graph)
        assert t is not None
        assert (t.old, t.new, t.field) == ("tentative", "accepted", "assent")

    def test_two_corroborations_from_same_source_stays_tentative(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/b.md")
        target = write_zettel(root, "20260101000001", assent="tentative")
        for zid in ("20260101000002", "20260101000003"):
            write_zettel(
                root,
                zid,
                sources=["sources/archive/2026-04/b.md"],
                links=[{"rel": "supports", "to": target}],
            )
        graph = VaultGraph.build(root)
        assert plan_assent(graph.zettels[target], graph) is None

    def test_open_disagreement_holds_assent(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/b.md")
        write_source(root, "sources/archive/2026-04/c.md")
        target = write_zettel(
            root,
            "20260101000001",
            assent="tentative",
            doubts=[{"mode": "disagreement", "claim": "c1", "rationale": "held"}],
        )
        write_zettel(
            root,
            "20260101000002",
            sources=["sources/archive/2026-04/b.md"],
            links=[{"rel": "supports", "to": target}],
        )
        write_zettel(
            root,
            "20260101000003",
            sources=["sources/archive/2026-04/c.md"],
            links=[{"rel": "supports", "to": target}],
        )
        graph = VaultGraph.build(root)
        assert plan_assent(graph.zettels[target], graph) is None

    def test_accepted_is_terminal_for_maintain(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        z = write_zettel(root, "20260101000001", assent="accepted")
        graph = VaultGraph.build(root)
        assert plan_assent(graph.zettels[z], graph) is None

    def test_own_sources_do_not_corroborate(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_source(root, "sources/archive/2026-04/a.md")
        write_source(root, "sources/archive/2026-04/b.md")
        # Two of its OWN sources, no supporters: not corroboration.
        z = write_zettel(
            root,
            "20260101000001",
            assent="tentative",
            sources=["sources/archive/2026-04/a.md", "sources/archive/2026-04/b.md"],
        )
        graph = VaultGraph.build(root)
        assert plan_assent(graph.zettels[z], graph) is None

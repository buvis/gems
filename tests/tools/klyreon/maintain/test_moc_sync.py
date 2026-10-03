"""Phase 1: MOC membership reconciliation."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.maintain.graph import VaultGraph
from klyreon.maintain.moc_sync import apply_moc_sync, plan_moc_sync
from klyreon.vault.git import GitIdentity

from tests.tools.klyreon.maintain.conftest import NOW, commit_all, write_moc, write_zettel

pytestmark = pytest.mark.klyreon

KLYREON = GitIdentity(name="klyreon", email="klyreon@localhost")


class TestPlan:
    def test_added_member_is_planned(self, tmp_path: Path) -> None:
        root = tmp_path / "v"
        for sub in ("wiki/notes", "wiki/mocs"):
            (root / sub).mkdir(parents=True)
        moc = write_moc(root, "architecture", [])
        z = write_zettel(root, "20260101000001", mocs=[moc])
        plan = plan_moc_sync(VaultGraph.build(root))
        assert not plan.is_empty
        assert plan.drifts[0].added == (z,)

    def test_removed_member_is_planned(self, tmp_path: Path) -> None:
        root = tmp_path / "v"
        for sub in ("wiki/notes", "wiki/mocs"):
            (root / sub).mkdir(parents=True)
        gone = "wiki/notes/20260101000099.md"
        write_moc(root, "architecture", [gone])
        plan = plan_moc_sync(VaultGraph.build(root))
        assert plan.drifts[0].removed == (gone,)

    def test_no_drift_plans_nothing(self, tmp_path: Path) -> None:
        root = tmp_path / "v"
        for sub in ("wiki/notes", "wiki/mocs"):
            (root / sub).mkdir(parents=True)
        z = write_zettel(root, "20260101000001", mocs=["wiki/mocs/architecture.md"])
        write_moc(root, "architecture", [z])
        assert plan_moc_sync(VaultGraph.build(root)).is_empty


class TestApply:
    def test_apply_adds_and_removes_preserving_prose(self, git_vault: Path) -> None:
        root = git_vault
        moc = write_moc(
            root,
            "architecture",
            ["wiki/notes/20260101000099.md"],  # stale member, will be removed
            prose_above="Entry room prose above.\n\n",
            prose_below="\n\nFooter prose below.",
        )
        write_zettel(root, "20260101000001", mocs=[moc])
        commit_all(root)

        graph = VaultGraph.build(root)
        plan = plan_moc_sync(graph)
        applied = apply_moc_sync(root, graph, plan, identity=KLYREON, now=NOW)
        assert len(applied) == 1

        text = (root / moc).read_text()
        assert "Entry room prose above." in text
        assert "Footer prose below." in text
        assert "wiki/notes/20260101000001.md" in text
        assert "20260101000099" not in text

    def test_second_sweep_plans_nothing(self, git_vault: Path) -> None:
        root = git_vault
        moc = write_moc(root, "architecture", [])
        z = write_zettel(root, "20260101000001", mocs=[moc])
        commit_all(root)

        graph = VaultGraph.build(root)
        apply_moc_sync(root, graph, plan_moc_sync(graph), identity=KLYREON, now=NOW)

        # Re-read and re-plan: nothing should drift now.
        assert plan_moc_sync(VaultGraph.build(root)).is_empty
        _ = z

"""Phase 1: prune-candidate detection and the grouped delete-plus-cleanup."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from klyreon.maintain.graph import VaultGraph
from klyreon.maintain.prune import find_candidates, prune
from klyreon.spec.validator import validate_vault
from klyreon.vault.git import GitIdentity

from tests.tools.klyreon.maintain.conftest import NOW, commit_all, make_vault, write_moc, write_zettel

pytestmark = pytest.mark.klyreon

KLYREON = GitIdentity(name="klyreon", email="klyreon@localhost")
OLD = NOW - dt.timedelta(days=400)


class TestFindCandidates:
    def test_backdated_orphan_is_a_candidate(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        z = write_zettel(root, "20260101000001", lifecycle="fleeting", updated=OLD)
        graph = VaultGraph.build(root)
        candidates = find_candidates(graph, window_days=365, now=NOW)
        assert [c.path for c in candidates] == [z]

    def test_recent_orphan_is_not_a_candidate(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_zettel(root, "20260101000001", lifecycle="fleeting", created=NOW, updated=NOW)
        graph = VaultGraph.build(root)
        assert find_candidates(graph, window_days=365, now=NOW) == []

    def test_rejected_is_exempt(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_zettel(root, "20260101000001", lifecycle="fleeting", assent="rejected", updated=OLD)
        graph = VaultGraph.build(root)
        assert find_candidates(graph, window_days=365, now=NOW) == []

    def test_delivered_as_is_exempt(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        write_zettel(
            root,
            "20260101000001",
            lifecycle="fleeting",
            delivered_as="shipped-feature",
            created=OLD,
            updated=OLD,
        )
        graph = VaultGraph.build(root)
        assert find_candidates(graph, window_days=365, now=NOW) == []

    def test_linked_is_not_a_candidate(self, tmp_path: Path) -> None:
        root = make_vault(tmp_path / "v")
        other = write_zettel(root, "20260101000002", lifecycle="literature", updated=OLD)
        write_zettel(
            root,
            "20260101000001",
            lifecycle="fleeting",
            created=OLD,
            updated=OLD,
            links=[{"rel": "supports", "to": other}],
        )
        graph = VaultGraph.build(root)
        paths = [c.path for c in find_candidates(graph, window_days=365, now=NOW)]
        assert "wiki/notes/20260101000001.md" not in paths


class TestPrune:
    def test_prune_removes_file_and_cleans_inbound_and_validates_clean(self, git_vault: Path) -> None:
        root = git_vault
        victim = write_zettel(root, "20260101000001", lifecycle="fleeting", updated=OLD)
        # An inbound link + a doubt target + MOC membership all name the victim.
        referrer = write_zettel(
            root,
            "20260101000002",
            lifecycle="literature",
            mocs=["wiki/mocs/architecture.md"],
            links=[{"rel": "supports", "to": victim}],
            doubts=[
                {
                    "mode": "disagreement",
                    "claim": "c1",
                    "rationale": "disputes the victim",
                    "target": {"to": victim, "claim": "c1"},
                },
            ],
        )
        write_moc(root, "architecture", [victim, referrer])
        commit_all(root)

        graph = VaultGraph.build(root)
        # The victim is linked FROM referrer, so it has inbound; force a pure
        # orphan by detecting on a victim with no links. Re-build a candidate
        # directly: the victim here is referenced, so detection would skip it.
        # Instead prune it explicitly to exercise the cleanup path.
        from klyreon.maintain.prune import PruneCandidate

        sha = prune(root, PruneCandidate(path=victim, reason="test"), graph, identity=KLYREON)
        assert sha

        assert not (root / victim).exists()
        ref_text = (root / referrer).read_text()
        assert victim not in ref_text  # inbound link + doubt target gone
        moc_text = (root / "wiki/mocs/architecture.md").read_text()
        assert "20260101000001" not in moc_text  # membership gone
        # The grouped commit leaves the vault validate-clean.
        assert validate_vault(root) == []

    def test_prune_is_one_commit(self, git_vault: Path) -> None:
        import subprocess

        root = git_vault
        victim = write_zettel(root, "20260101000001", lifecycle="fleeting", updated=OLD)
        referrer = write_zettel(
            root,
            "20260101000002",
            lifecycle="literature",
            mocs=["wiki/mocs/architecture.md"],
            links=[{"rel": "supports", "to": victim}],
        )
        write_moc(root, "architecture", [victim, referrer])
        commit_all(root)

        before = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        from klyreon.maintain.prune import PruneCandidate

        prune(root, PruneCandidate(path=victim, reason="test"), VaultGraph.build(root), identity=KLYREON)
        after = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert int(after) - int(before) == 1

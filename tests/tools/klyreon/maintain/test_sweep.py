"""Phase 2: the maintain sweep and CommandMaintain, end to end."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from klyreon.commands.maintain import CommandMaintain
from klyreon.maintain.sweep import run_maintain
from klyreon.spec.model import FileKind
from klyreon.spec.parser import parse_file
from klyreon.spec.validator import validate_vault
from klyreon.vault.git import GitIdentity

from tests.tools.klyreon.maintain.conftest import NOW, commit_all, write_moc, write_source, write_zettel

pytestmark = pytest.mark.klyreon

KLYREON = GitIdentity(name="klyreon", email="klyreon@localhost")


def _lifecycle(root: Path, rel: str) -> str:
    return str(parse_file(root / rel, FileKind.ZETTEL).get("lifecycle"))


def _assent(root: Path, rel: str) -> str:
    return str(parse_file(root / rel, FileKind.ZETTEL).get("assent"))


def _processed(root: Path, rel: str) -> object:
    return parse_file(root / rel, FileKind.ZETTEL).get("processed")


def _promotable_vault(root: Path) -> tuple[str, str]:
    """Seed one promotable (fleeting->literature) and one corroborated (assent) zettel.

    Every concept zettel anchors to the MOC (orphan-concept is a lint rule), and
    the supporters are already terminal (evergreen/accepted) so only the two
    subjects transition — keeping the expected count at exactly 2.
    """
    write_source(root, "sources/archive/2026-04/a.md")
    write_source(root, "sources/archive/2026-04/b.md")
    write_source(root, "sources/archive/2026-04/c.md")
    moc = write_moc(root, "architecture", [])

    # Promotable: fleeting, sourced, linked, anchored.
    promotable = write_zettel(
        root,
        "20260101000001",
        lifecycle="fleeting",
        assent="unknown",
        processed=True,
        sources=["sources/archive/2026-04/a.md"],
        links=[{"rel": "supports", "to": "wiki/notes/20260101000010.md"}],
        mocs=[moc],
    )
    # The target of that link: already terminal so it does not transition.
    write_zettel(root, "20260101000010", lifecycle="evergreen", assent="accepted", mocs=[moc])

    # Corroborated: tentative, two distinct supporters w/ distinct sources.
    corroborated = write_zettel(root, "20260101000002", lifecycle="literature", assent="tentative", mocs=[moc])
    write_zettel(
        root,
        "20260101000003",
        lifecycle="evergreen",
        assent="accepted",
        sources=["sources/archive/2026-04/b.md"],
        links=[{"rel": "supports", "to": corroborated}],
        mocs=[moc],
    )
    write_zettel(
        root,
        "20260101000004",
        lifecycle="evergreen",
        assent="accepted",
        sources=["sources/archive/2026-04/c.md"],
        links=[{"rel": "supports", "to": corroborated}],
        mocs=[moc],
    )
    return promotable, corroborated


class TestSweep:
    def test_applies_transitions_and_preserves_processed(self, git_vault: Path) -> None:
        root = git_vault
        promotable, corroborated = _promotable_vault(root)
        commit_all(root)

        result = run_maintain(root, identity=KLYREON, now=NOW)

        assert _lifecycle(root, promotable) == "literature"
        assert _assent(root, corroborated) == "accepted"
        assert _processed(root, promotable) is True  # never reset
        assert result.trail is not None
        assert validate_vault(root) == []

    def test_writes_one_maintain_trail(self, git_vault: Path) -> None:
        root = git_vault
        _promotable_vault(root)
        commit_all(root)
        result = run_maintain(root, identity=KLYREON, now=NOW)
        trail_text = (root / result.trail).read_text()
        assert "run: maintain" in trail_text
        assert "## Transitions" in trail_text

    def test_second_sweep_changes_nothing(self, git_vault: Path) -> None:
        root = git_vault
        _promotable_vault(root)
        commit_all(root)
        run_maintain(root, identity=KLYREON, now=NOW)
        head1 = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout
        result2 = run_maintain(root, identity=KLYREON, now=NOW)
        # The second sweep plans no transitions and no MOC drift.
        assert result2.transitions == []
        assert result2.moc_reconciled == []
        # Only the trail commit lands on the second sweep.
        head2 = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout
        assert head1 != head2  # trail committed
        assert result2.trail is not None

    def test_dry_run_writes_nothing(self, git_vault: Path) -> None:
        root = git_vault
        promotable, _ = _promotable_vault(root)
        commit_all(root)
        head_before = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout

        result = run_maintain(root, identity=KLYREON, now=NOW, dry_run=True)
        assert result.transitions  # it REPORTS transitions
        assert result.trail is None  # but writes nothing
        assert _lifecycle(root, promotable) == "fleeting"  # unchanged on disk
        head_after = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout
        assert head_before == head_after
        # No new trail file either.
        assert list((root / "wiki" / "trails").glob("*.md")) == []

    def test_resume_after_interruption_finishes_the_rest(self, git_vault: Path) -> None:
        root = git_vault
        promotable, corroborated = _promotable_vault(root)
        commit_all(root)

        # Simulate an interruption: apply ONLY the promotable's lifecycle, commit it,
        # leave the rest. A full re-run must finish the assent transition.
        from klyreon.spec.writer import write_document
        from klyreon.vault.git import commit as git_commit

        doc = parse_file(root / promotable, FileKind.ZETTEL)
        doc.frontmatter["lifecycle"] = "literature"
        write_document(doc, root / promotable)
        git_commit(root, [promotable], "maintain: partial", KLYREON)
        assert validate_vault(root) == []  # validate-clean after partial

        run_maintain(root, identity=KLYREON, now=NOW)
        assert _assent(root, corroborated) == "accepted"  # the remainder landed
        assert validate_vault(root) == []


class TestCommandMaintain:
    def test_refuses_non_git_vault(self, tmp_path: Path) -> None:
        from tests.tools.klyreon.maintain.conftest import make_vault

        root = make_vault(tmp_path / "v")
        result = CommandMaintain(root, identity=KLYREON, now=NOW).execute()
        assert result.success is False
        assert "git work tree" in (result.error or "")

    def test_success_on_clean_vault(self, git_vault: Path) -> None:
        root = git_vault
        _promotable_vault(root)
        commit_all(root)
        result = CommandMaintain(root, identity=KLYREON, now=NOW).execute()
        assert result.success is True
        # 000001 lifecycle, 000002 assent AND 000002 literature->evergreen (two distinct sources).
        assert result.metadata["transitions"] == 3

    def test_lint_errors_fail_but_transitions_apply(self, git_vault: Path) -> None:
        root = git_vault
        _promotable_vault(root)
        # Introduce a lint error: a dangling source reference.
        write_zettel(
            root,
            "20260101000020",
            lifecycle="fleeting",
            sources=["sources/archive/2026-04/does-not-exist.md"],
        )
        commit_all(root)
        result = CommandMaintain(root, identity=KLYREON, now=NOW).execute()
        assert result.success is False  # exit 1 on lint errors
        assert result.metadata["lint_errors"] >= 1
        # Transitions still applied despite the lint finding.
        assert result.metadata["transitions"] >= 2

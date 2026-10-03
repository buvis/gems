"""Criterion-4 stand-in: a scheduled run over a mixed corpus, headless.

This is the CI-side stand-in the PRD's Phase-2 exit criteria name for discovery
criterion 4 (whose literal form is a 7-day live cron soak the owner runs
post-merge). It seeds a mixed corpus where at least one claim reaches its second
corroboration inside the window, runs maintain with zero human input, and
asserts: ``validate`` stays clean, the run does not hang, and the
``literature`` + ``evergreen`` count is higher at the end than at the start.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.commands.maintain import CommandMaintain
from klyreon.commands.status import CommandStatus
from klyreon.spec.validator import validate_vault
from klyreon.vault.git import GitIdentity

from tests.tools.klyreon.maintain.conftest import NOW, commit_all, write_moc, write_source, write_zettel

pytestmark = pytest.mark.klyreon

KLYREON = GitIdentity(name="klyreon", email="klyreon@localhost")


def _distilled_count(root: Path) -> int:
    md = CommandStatus(root, now=NOW).execute().metadata
    lifecycle = md["lifecycle"]
    assert isinstance(lifecycle, dict)
    return lifecycle.get("literature", 0) + lifecycle.get("evergreen", 0)


def _seed_mixed_corpus(root: Path) -> None:
    for name in ("a", "b", "c", "d"):
        write_source(root, f"sources/archive/2026-04/{name}.md", title=f"Source {name}")
    moc = write_moc(root, "architecture", [])

    # A fleeting, sourced, linked zettel -> will reach literature.
    write_zettel(
        root,
        "20260101000001",
        lifecycle="fleeting",
        assent="unknown",
        sources=["sources/archive/2026-04/a.md"],
        links=[{"rel": "supports", "to": "wiki/notes/20260101000002.md"}],
        mocs=[moc],
    )
    # A tentative claim that reaches its SECOND corroboration this window ->
    # accepted; it is already literature and its two supporters give it two
    # distinct sources -> also evergreen.
    write_zettel(root, "20260101000002", lifecycle="literature", assent="tentative", mocs=[moc])
    write_zettel(
        root,
        "20260101000003",
        lifecycle="evergreen",
        assent="accepted",
        sources=["sources/archive/2026-04/c.md"],
        links=[{"rel": "supports", "to": "wiki/notes/20260101000002.md"}],
        mocs=[moc],
    )
    write_zettel(
        root,
        "20260101000004",
        lifecycle="evergreen",
        assent="accepted",
        sources=["sources/archive/2026-04/d.md"],
        links=[{"rel": "supports", "to": "wiki/notes/20260101000002.md"}],
        mocs=[moc],
    )


class TestCriterionFour:
    def test_headless_run_validates_clean_and_distillation_rises(self, git_vault: Path) -> None:
        root = git_vault
        _seed_mixed_corpus(root)
        commit_all(root)

        before = _distilled_count(root)
        assert validate_vault(root) == []

        # Zero human input: the command takes defaults and makes no LLM call.
        result = CommandMaintain(root, identity=KLYREON, now=NOW).execute()
        assert result.success is True

        after = _distilled_count(root)
        assert after > before, f"distilled count did not rise: {before} -> {after}"
        assert validate_vault(root) == []  # stays clean after the sweep

        # status reports mean links per zettel (a number) and the distilled count.
        status_md = CommandStatus(root, now=NOW).execute().metadata
        assert isinstance(status_md["mean_links"], float)

    def test_second_headless_run_is_a_no_op_on_content(self, git_vault: Path) -> None:
        root = git_vault
        _seed_mixed_corpus(root)
        commit_all(root)
        CommandMaintain(root, identity=KLYREON, now=NOW).execute()
        second = CommandMaintain(root, identity=KLYREON, now=NOW).execute()
        assert second.metadata["transitions"] == 0
        assert second.metadata["moc_reconciled"] == 0

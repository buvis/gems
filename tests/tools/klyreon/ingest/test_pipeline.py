"""Phase 2: the ingest pipeline, CommandIngest, run bounds."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import ModuleType

import pytest
from klyreon.backends.base import BackendError, BackendReason, IngestPayload, PayloadClaim, ZettelDraft
from klyreon.backends.stub import StubBackend
from klyreon.commands.ingest import CommandIngest
from klyreon.spec.validator import validate_vault

from .conftest import load_payloads

pytestmark = pytest.mark.klyreon

NOW = dt.datetime(2026, 5, 10, 9, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2)))


def _marker_stub() -> StubBackend:
    payloads: ModuleType = load_payloads()
    return StubBackend(by_marker=payloads.all_markers())


class TestNonGitRefuses:
    def test_non_git_vault_exits_1(self, tmp_path: Path) -> None:
        root = tmp_path / "plain"
        for sub in ("sources", "wiki/notes", "wiki/mocs", "wiki/trails"):
            (root / sub).mkdir(parents=True)
        result = CommandIngest(root, backend=StubBackend()).execute()
        assert result.success is False
        assert "git work tree" in (result.error or "")


class TestHappyPath:
    def test_four_sources_commit_and_validate_clean(self, git_happy_vault: Path) -> None:
        result = CommandIngest(git_happy_vault, backend=_marker_stub(), now=NOW).execute()
        assert result.success, result.error
        # Four commits + the trail.
        assert result.metadata["committed"] == 4
        assert result.metadata["failed"] == 0
        assert result.metadata["trail"]
        # Vault validates clean after ingest.
        assert not validate_vault(git_happy_vault)
        # Each source moved to the archive.
        assert not list((git_happy_vault / "sources" / "2026-05").glob("*.md"))
        assert list((git_happy_vault / "sources" / "archive").rglob("*.md"))
        # A trail landed and validates as kind: trail.
        trails = list((git_happy_vault / "wiki" / "trails").glob("*.md"))
        assert len(trails) == 1


class TestRunBounds:
    def test_cap_commits_five_defers_two(self, git_happy_vault: Path) -> None:
        # Add three more sources so the inbox holds seven; give the stub a
        # generic payload for each extra via a shared marker.
        extra_payload = IngestPayload(
            zettels=[
                ZettelDraft(
                    title="Extra",
                    concept_type="observation",
                    claims=[PayloadClaim(id="c1", statement="s")],
                    mocs=["wiki/mocs/architecture.md"],
                ),
            ],
        )
        markers = load_payloads().all_markers()
        for i in range(3):
            name = f"extra-{i}"
            content = (
                f"---\nid: {name}\ntitle: Extra {i}\n"
                "created: 2026-05-01T09:00:00+02:00\ntype: article\n---\n\n"
                f"# Extra {i}\n\n<!-- stub-marker: {name} -->\nbody\n"
            )
            (git_happy_vault / "sources" / "2026-05" / f"{name}.md").write_text(content, encoding="utf-8")
            markers[name] = extra_payload
        stub = StubBackend(by_marker=markers)

        result = CommandIngest(git_happy_vault, backend=stub, max_sources=5, now=NOW).execute()
        assert result.success, result.error
        assert result.metadata["committed"] == 5
        assert result.metadata["deferred"] == 2


class TestTimeoutIsolation:
    def test_timeout_on_one_source_leaves_it_untouched_and_continues(self, git_happy_vault: Path) -> None:
        markers = load_payloads().all_markers()

        class TimeoutOnOne(StubBackend):
            def run(self, prompt: str, timeout: int) -> IngestPayload:
                if "transcript-arch-review-2026-05-01" in prompt:
                    raise BackendError(BackendReason.TIMEOUT, "simulated timeout")
                return super().run(prompt, timeout)

        stub = TimeoutOnOne(by_marker=markers)
        result = CommandIngest(git_happy_vault, backend=stub, now=NOW).execute()
        # One source failed (the timed-out one); the rest committed.
        assert result.metadata["failed"] == 1
        assert result.metadata["committed"] == 3
        # The timed-out source stays in the inbox (untouched).
        assert (git_happy_vault / "sources" / "2026-05" / "transcript-arch-review-2026-05-01.md").is_file()
        # The vault still validates clean (no partial write for the failed source).
        assert not validate_vault(git_happy_vault)
        # Overall exit is failure because a source failed.
        assert result.success is False


class TestDryRun:
    def test_dry_run_applies_nothing(self, git_happy_vault: Path) -> None:
        before = sorted(p.name for p in (git_happy_vault / "wiki" / "notes").glob("*.md"))
        result = CommandIngest(git_happy_vault, backend=_marker_stub(), dry_run=True, now=NOW).execute()
        assert result.success
        after = sorted(p.name for p in (git_happy_vault / "wiki" / "notes").glob("*.md"))
        assert before == after  # nothing written
        # Sources still in the inbox.
        assert list((git_happy_vault / "sources" / "2026-05").glob("*.md"))

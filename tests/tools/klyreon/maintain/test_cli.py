"""Phase 2: the maintain and schedule commands driven through the Click CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from klyreon.cli import cli

from tests.tools.klyreon.maintain.conftest import commit_all, make_vault, write_moc, write_source, write_zettel

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.klyreon


def _norm(output: str) -> str:
    return " ".join(output.split())


class TestMaintainCLI:
    def test_maintain_non_git_exits_1(
        self, tmp_path: Path, runner: CliRunner, klyreon_env: Callable[[Path], None]
    ) -> None:
        root = make_vault(tmp_path / "vault")
        klyreon_env(root)
        res = runner.invoke(cli, ["maintain"])
        assert res.exit_code == 1
        assert "not inside a git work tree" in _norm(res.output)

    def test_maintain_dry_run_reports_without_writing(
        self, git_vault: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = git_vault
        monkeypatch.setenv("KLYREON_ROOT", str(root))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(root.parent / "config"))
        write_source(root, "sources/archive/2026-04/a.md")
        moc = write_moc(root, "architecture", [])
        write_zettel(
            root,
            "20260101000010",
            lifecycle="evergreen",
            assent="accepted",
            mocs=[moc],
        )
        write_zettel(
            root,
            "20260101000001",
            lifecycle="fleeting",
            assent="unknown",
            sources=["sources/archive/2026-04/a.md"],
            links=[{"rel": "supports", "to": "wiki/notes/20260101000010.md"}],
            mocs=[moc],
        )
        commit_all(root)
        res = runner.invoke(cli, ["maintain", "--dry-run"])
        assert res.exit_code == 0, res.output
        assert "dry-run" in _norm(res.output)
        # No trail written under dry-run.
        assert list((root / "wiki" / "trails").glob("*.md")) == []


class TestScheduleCLI:
    def test_schedule_status_not_installed(
        self, tmp_path: Path, runner: CliRunner, klyreon_env: Callable[[Path], None]
    ) -> None:
        root = make_vault(tmp_path / "vault")
        klyreon_env(root)
        res = runner.invoke(cli, ["schedule", "status"])
        assert res.exit_code == 0, res.output
        assert "not installed" in _norm(res.output)

    def test_schedule_install_bad_time_exits_1(
        self, tmp_path: Path, runner: CliRunner, klyreon_env: Callable[[Path], None]
    ) -> None:
        root = make_vault(tmp_path / "vault")
        klyreon_env(root)
        res = runner.invoke(cli, ["schedule", "install", "--at", "99:99"])
        assert res.exit_code == 1
        assert "--at" in _norm(res.output)


class TestInitScheduleOffer:
    def test_no_input_skips_and_prints_followup(
        self, tmp_path: Path, runner: CliRunner, klyreon_env: Callable[[Path], None]
    ) -> None:
        root = tmp_path / "vault"
        klyreon_env(root)
        res = runner.invoke(cli, ["init", str(root), "--no-input"])
        assert res.exit_code == 0, res.output
        assert "klyreon schedule install" in _norm(res.output)


class TestStatusPruneLine:
    def test_status_shows_prune_candidate_count_and_mode(
        self, tmp_path: Path, runner: CliRunner, klyreon_env: Callable[[Path], None]
    ) -> None:
        root = make_vault(tmp_path / "vault")
        klyreon_env(root)
        res = runner.invoke(cli, ["status"])
        assert res.exit_code == 0, res.output
        normalized = _norm(res.output)
        assert "prune candidates:" in normalized
        assert "report-only" in normalized

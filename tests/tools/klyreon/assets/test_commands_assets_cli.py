"""Phase 2 -- the assets subcommands and the setup path, through the Click CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from klyreon.cli import cli

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.klyreon


@pytest.fixture
def home_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return home


def _skill(home: Path) -> Path:
    return home / ".claude" / "skills" / "klyreon" / "SKILL.md"


def _norm(output: str) -> str:
    # Rich word-wraps at an env-dependent width; normalise before substring checks.
    return " ".join(output.split())


class TestAssetsInstall:
    def test_install_claude_happy_path(self, home_env: Path, runner: CliRunner) -> None:
        res = runner.invoke(cli, ["assets", "install", "--operator", "claude"])
        assert res.exit_code == 0, res.output
        assert _skill(home_env).is_file()
        assert "install complete" in _norm(res.output)

    def test_install_no_operator_empty_manifest_exits_1(self, home_env: Path, runner: CliRunner) -> None:
        res = runner.invoke(cli, ["assets", "install"])
        assert res.exit_code == 1
        assert "no operator given" in _norm(res.output)

    def test_install_unknown_operator_exits_1_naming_valid(self, home_env: Path, runner: CliRunner) -> None:
        res = runner.invoke(cli, ["assets", "install", "--operator", "emacs"])
        assert res.exit_code == 1
        normalized = _norm(res.output)
        assert "unknown operator" in normalized
        assert "claude" in normalized

    def test_install_then_default_targets_installed(self, home_env: Path, runner: CliRunner) -> None:
        runner.invoke(cli, ["assets", "install", "--operator", "claude"])
        res = runner.invoke(cli, ["assets", "install"])
        assert res.exit_code == 0, res.output
        assert "current" in _norm(res.output)


class TestAssetsStatus:
    def test_status_empty(self, home_env: Path, runner: CliRunner) -> None:
        res = runner.invoke(cli, ["assets", "status"])
        assert res.exit_code == 0
        assert "no assets installed" in _norm(res.output)

    def test_status_reports_installed(self, home_env: Path, runner: CliRunner) -> None:
        runner.invoke(cli, ["assets", "install", "--operator", "claude"])
        res = runner.invoke(cli, ["assets", "status"])
        assert res.exit_code == 0, res.output
        assert "claude" in _norm(res.output)
        assert "current" in _norm(res.output)


class TestAssetsRefresh:
    def test_refresh_empty(self, home_env: Path, runner: CliRunner) -> None:
        res = runner.invoke(cli, ["assets", "refresh"])
        assert res.exit_code == 0
        assert "nothing" in _norm(res.output).lower()

    def test_refresh_reinstalls(self, home_env: Path, runner: CliRunner) -> None:
        runner.invoke(cli, ["assets", "install", "--operator", "claude"])
        _skill(home_env).write_text("drift\n", encoding="utf-8")
        res = runner.invoke(cli, ["assets", "refresh"])
        assert res.exit_code == 0, res.output
        assert "refresh complete" in _norm(res.output)


class TestAssetsUninstall:
    def test_uninstall_removes(self, home_env: Path, runner: CliRunner) -> None:
        runner.invoke(cli, ["assets", "install", "--operator", "claude"])
        res = runner.invoke(cli, ["assets", "uninstall", "--operator", "claude"])
        assert res.exit_code == 0, res.output
        assert not _skill(home_env).exists()
        assert "uninstall complete" in _norm(res.output)

    def test_uninstall_keeps_edited(self, home_env: Path, runner: CliRunner) -> None:
        runner.invoke(cli, ["assets", "install", "--operator", "claude"])
        _skill(home_env).write_text("mine\n", encoding="utf-8")
        res = runner.invoke(cli, ["assets", "uninstall", "--operator", "claude"])
        assert res.exit_code == 0
        assert _skill(home_env).exists()
        assert "kept" in _norm(res.output)


class TestInitOffer:
    def test_init_with_operator_installs_without_prompt(
        self,
        home_env: Path,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("klyreon.commands.init.is_git_vault", lambda _root: True)
        root = tmp_path / "vault"
        res = runner.invoke(cli, ["init", str(root), "--operator", "claude"])
        assert res.exit_code == 0, res.output
        assert _skill(home_env).is_file()
        assert "asset written" in _norm(res.output)

    def test_init_non_tty_skips_offer_and_prints_followup(
        self,
        home_env: Path,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("klyreon.commands.init.is_git_vault", lambda _root: True)
        root = tmp_path / "vault"
        # CliRunner's stdin is not a TTY, so the offer must be skipped.
        res = runner.invoke(cli, ["init", str(root)])
        assert res.exit_code == 0, res.output
        assert not _skill(home_env).exists()
        assert "klyreon assets install" in _norm(res.output)

    def test_init_no_input_skips_offer(
        self,
        home_env: Path,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("klyreon.commands.init.is_git_vault", lambda _root: True)
        root = tmp_path / "vault"
        res = runner.invoke(cli, ["init", str(root), "--no-input"])
        assert res.exit_code == 0, res.output
        assert not _skill(home_env).exists()


class TestStatusBehindWarning:
    def test_status_warns_once_when_asset_behind(
        self,
        home_env: Path,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Create a vault and point $KLYREON_ROOT at it so `status` resolves.
        root = tmp_path / "vault"
        for sub in ("sources", "wiki/notes", "wiki/mocs", "wiki/trails"):
            (root / sub).mkdir(parents=True)
        monkeypatch.setenv("KLYREON_ROOT", str(root))
        monkeypatch.setattr("klyreon.commands.status.is_git_vault", lambda _root: True)
        monkeypatch.setattr("klyreon.cli._warn_if_maintenance_stale", lambda _ctx: None)

        # Install, then force the recorded version behind the CLI.
        runner.invoke(cli, ["assets", "install", "--operator", "claude"])
        from klyreon.assets.manifest import ManifestEntry, load_manifest, save_manifest

        m = load_manifest()
        target = _skill(home_env)
        entry = m.entry_for_path(str(target))
        assert entry is not None
        m.upsert(ManifestEntry("asset", "claude", str(target), entry.sha256, "0.0.1", entry.installed_at))
        save_manifest(m)

        res = runner.invoke(cli, ["status"])
        assert res.exit_code == 0, res.output
        normalized = _norm(res.output)
        assert "behind this klyreon" in normalized
        assert normalized.count("behind this klyreon") == 1, "the warning must appear exactly once"

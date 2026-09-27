from __future__ import annotations

from unittest.mock import patch

import click

from backup.cli import cli
from backup.config import BackupConfig
from backup.step_result import StepResult


def _cfg(instances: dict[str, dict[str, object]]) -> BackupConfig:
    return BackupConfig.model_validate({"instances": instances})


class TestBackupCliShape:
    def test_cli_is_a_single_command_not_a_group(self) -> None:
        assert isinstance(cli, click.Command)
        assert not isinstance(cli, click.Group)

    def test_help_lists_filters(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--only" in result.output
        assert "--tag" in result.output
        assert "--list" in result.output
        assert "--dry-run" in result.output


class TestBackupCliRun:
    def test_runs_all_applicable_and_renders_via_console(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch(
                "backup.runner.Runner.run",
                return_value=iter([StepResult("git-src", True, "archived 3 files -> /x (99 bytes)")]),
            ),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "archived 3 files" in result.output

    def test_only_narrows_selection(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}, "docs": {"use": "tar-archive"}})
        plan = [("git-src", cfg.instances["git-src"]), ("docs", cfg.instances["docs"])]
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            captured["selected"] = [n for n, _ in selected]
            return iter([])

        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--only", "docs"])
        assert result.exit_code == 0
        assert captured["selected"] == ["docs"]

    def test_tag_narrows_selection(self, runner) -> None:
        cfg = _cfg(
            {
                "git-src": {"use": "tar-archive", "tags": ["code"]},
                "docs": {"use": "tar-archive", "tags": ["nightly"]},
            },
        )
        plan = [("git-src", cfg.instances["git-src"]), ("docs", cfg.instances["docs"])]
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            captured["selected"] = [n for n, _ in selected]
            return iter([])

        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--tag", "nightly"])
        assert result.exit_code == 0
        assert captured["selected"] == ["docs"]

    def test_only_unknown_reports(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch("backup.runner.Runner.run", return_value=iter([])),
        ):
            result = runner.invoke(cli, ["--only", "nope"])
        assert result.exit_code == 0
        assert "unknown instance 'nope'" in result.output


class TestBackupCliList:
    def test_list_prints_plan_and_runs_nothing(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive", "order": 10}})
        plan = [("git-src", cfg.instances["git-src"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--list"])
        assert result.exit_code == 0
        assert "git-src" in result.output
        assert mock_run.call_count == 0

    def test_list_empty_plan(self, runner) -> None:
        cfg = _cfg({})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[]),
        ):
            result = runner.invoke(cli, ["--list"])
        assert result.exit_code == 0
        assert "no configured instances" in result.output


class TestBackupCliDryRun:
    def test_dry_run_passes_flag_to_runner(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        plan = [("git-src", cfg.instances["git-src"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch("backup.runner.Runner.__init__", return_value=None) as mock_init,
            patch("backup.runner.Runner.run", return_value=iter([])),
        ):
            result = runner.invoke(cli, ["--dry-run"])
        assert result.exit_code == 0
        assert mock_init.call_args.kwargs.get("dry_run") is True


class TestBackupCliErrors:
    def test_config_fatal_error_panics_not_traceback(self, runner) -> None:
        from buvis.pybase.result import FatalError

        with patch("backup.config.load_config", side_effect=FatalError("bad config")):
            result = runner.invoke(cli, [])
        assert "bad config" in result.output
        assert "Traceback" not in result.output


class TestBackupCliExitCode:
    """FIX B: a failed step must make the process exit nonzero (cron must not
    treat an incomplete backup as success), while every step is still rendered."""

    def test_failing_step_exits_nonzero_but_renders_all(self, runner) -> None:
        cfg = _cfg({"a": {"use": "tar-archive"}, "b": {"use": "tar-archive"}})
        plan = [("a", cfg.instances["a"]), ("b", cfg.instances["b"])]
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=plan),
            patch(
                "backup.runner.Runner.run",
                return_value=iter(
                    [
                        StepResult("a", False, "a failed: source not found"),
                        StepResult("b", True, "archived 2 files -> /x"),
                    ],
                ),
            ),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code != 0
        # both steps rendered — the failure did not short-circuit the success line
        assert "a failed" in result.output
        assert "archived 2 files" in result.output

    def test_all_success_exits_zero(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch(
                "backup.runner.Runner.run",
                return_value=iter([StepResult("git-src", True, "archived 3 files -> /x")]),
            ),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0


class TestBackupCliForGuard:
    """FIX H: --for is meaningful only with --show-excludes; alone it must not
    run a backup and must report the misuse."""

    def test_for_without_show_excludes_does_not_run_and_reports(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive"}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.config.applicable_instances", return_value=[("git-src", cfg.instances["git-src"])]),
            patch("backup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--for", "/some/path"])
        assert result.exit_code != 0
        assert "--for requires --show-excludes" in result.output
        assert mock_run.call_count == 0

    def test_show_excludes_with_for_still_works(self, runner) -> None:
        cfg = _cfg({"git-src": {"use": "tar-archive", "with": {"source": "/x", "out": "/o.tgz"}}})
        with (
            patch("backup.config.load_config", return_value=cfg),
            patch("backup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--show-excludes", "git-src", "--for", "/x/sub"])
        assert result.exit_code == 0
        assert "--for requires --show-excludes" not in result.output
        assert mock_run.call_count == 0

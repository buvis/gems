from __future__ import annotations

from unittest.mock import patch

import click

from sysup.cli import cli
from sysup.config import SysupConfig
from sysup.step_result import StepResult


def _cfg(commands: dict[str, dict[str, object]], prime: tuple[str, ...] = ()) -> SysupConfig:
    return SysupConfig.model_validate({"commands": commands, "prime": list(prime)})


class TestSysupCliShape:
    def test_cli_is_a_single_command_not_a_group(self) -> None:
        assert isinstance(cli, click.Command)
        assert not isinstance(cli, click.Group)

    def test_no_subcommands(self) -> None:
        # The mac/pip/nvim/wsl subcommands were removed in the cutover.
        assert not hasattr(cli, "commands") or not getattr(cli, "commands", {})

    def test_help_lists_filters_not_subcommands(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "--only" in result.output
        assert "--tag" in result.output
        assert "--list" in result.output
        assert "--dry-run" in result.output
        assert "mac" not in result.output


class TestSysupCliRun:
    def test_runs_all_applicable(self, runner) -> None:
        cfg = _cfg({"brew": {"steps": [["brew", "update"]]}})
        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=[("brew", cfg.commands["brew"])]),
            patch("sysup.runner.Runner.run", return_value=iter([StepResult("brew", True, "brew updated")])),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "brew updated" in result.output

    def test_only_narrows_selection(self, runner) -> None:
        cfg = _cfg(
            {
                "brew": {"steps": [["brew"]]},
                "uv": {"steps": [["uv"]]},
            },
        )
        plan = [("brew", cfg.commands["brew"]), ("uv", cfg.commands["uv"])]
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            captured["selected"] = [n for n, _ in selected]
            return iter([])

        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=plan),
            patch("sysup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--only", "uv"])
        assert result.exit_code == 0
        assert captured["selected"] == ["uv"]

    def test_tag_narrows_selection(self, runner) -> None:
        cfg = _cfg(
            {
                "brew": {"steps": [["brew"]], "tags": ["mac"]},
                "pkgs": {"use": "pip-outdated", "tags": ["python"]},
            },
        )
        plan = [("brew", cfg.commands["brew"]), ("pkgs", cfg.commands["pkgs"])]
        captured: dict[str, object] = {}

        def _fake_run(self, selected):
            captured["selected"] = [n for n, _ in selected]
            return iter([])

        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=plan),
            patch("sysup.runner.Runner.run", _fake_run),
        ):
            result = runner.invoke(cli, ["--tag", "python"])
        assert result.exit_code == 0
        assert captured["selected"] == ["pkgs"]

    def test_only_non_applicable_key_reports_skip(self, runner) -> None:
        cfg = _cfg({"brew": {"when": {"os": "darwin"}, "steps": [["brew"]]}})
        # brew is a known command but does NOT apply on this host (empty plan).
        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=[]),
            patch("sysup.runner.Runner.run", return_value=iter([])),
        ):
            result = runner.invoke(cli, ["--only", "brew"])
        assert result.exit_code == 0
        assert "does not apply on this host" in result.output

    def test_only_unknown_key_reports(self, runner) -> None:
        cfg = _cfg({"brew": {"steps": [["brew"]]}})
        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=[("brew", cfg.commands["brew"])]),
            patch("sysup.runner.Runner.run", return_value=iter([])),
        ):
            result = runner.invoke(cli, ["--only", "nope"])
        assert result.exit_code == 0
        assert "unknown command 'nope'" in result.output


class TestSysupCliList:
    def test_list_prints_plan_and_runs_nothing(self, runner) -> None:
        cfg = _cfg({"brew": {"order": 10, "when": {"os": "darwin", "check": "brew"}, "steps": [["brew"]]}})
        plan = [("brew", cfg.commands["brew"])]
        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=plan),
            patch("sysup.runner.Runner.run") as mock_run,
        ):
            result = runner.invoke(cli, ["--list"])
        assert result.exit_code == 0
        assert "brew" in result.output
        assert mock_run.call_count == 0

    def test_list_empty_plan(self, runner) -> None:
        cfg = _cfg({})
        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=[]),
        ):
            result = runner.invoke(cli, ["--list"])
        assert result.exit_code == 0
        assert "no applicable commands" in result.output


class TestSysupCliDryRun:
    def test_dry_run_passes_flag_to_runner(self, runner) -> None:
        cfg = _cfg({"brew": {"steps": [["brew"]]}})
        plan = [("brew", cfg.commands["brew"])]
        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=plan),
            patch("sysup.runner.Runner.__init__", return_value=None) as mock_init,
            patch("sysup.runner.Runner.run", return_value=iter([])),
        ):
            result = runner.invoke(cli, ["--dry-run"])
        assert result.exit_code == 0
        assert mock_init.call_args.kwargs.get("dry_run") is True


class TestSysupCliErrors:
    def test_config_fatal_error_panics_not_traceback(self, runner) -> None:
        from buvis.pybase.result import FatalError

        with patch("sysup.config.load_config", side_effect=FatalError("bad config")):
            result = runner.invoke(cli, [])
        assert "bad config" in result.output
        assert "Traceback" not in result.output

    def test_runner_fatal_error_panics(self, runner) -> None:
        from buvis.pybase.result import FatalError

        cfg = _cfg({"nvim": {"use": "nvim-mason"}})
        plan = [("nvim", cfg.commands["nvim"])]
        with (
            patch("sysup.config.load_config", return_value=cfg),
            patch("sysup.config.applicable_commands", return_value=plan),
            patch("sysup.runner.Runner.run", side_effect=FatalError("nvim not found")),
        ):
            result = runner.invoke(cli, [])
        assert "nvim not found" in result.output
        assert "Traceback" not in result.output


class TestSysupCliConfigForwarding:
    """The --config / --config-dir selection reaches load_config (PRD 00084, review #181)."""

    def test_config_and_config_dir_forwarded_to_load_config(self, runner, tmp_path) -> None:
        cfg = _cfg({"brew": {"steps": [["brew", "update"]]}})
        cfg_file = tmp_path / "buvis-sysup.yaml"
        cfg_file.write_text("commands:\n  brew:\n    steps:\n      - [brew, update]\n")
        with (
            patch("sysup.config.load_config", return_value=cfg) as mock_load,
            patch("sysup.config.applicable_commands", return_value=[("brew", cfg.commands["brew"])]),
            patch("sysup.runner.Runner.run", return_value=iter([StepResult("brew", True, "ok")])),
        ):
            result = runner.invoke(cli, ["--config", str(cfg_file), "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        mock_load.assert_called_once()
        _, kwargs = mock_load.call_args
        # Both the file and the dir the wrapper resolved settings from are forwarded,
        # so a regression dropping either arg fails here (the reviewer's concern).
        assert kwargs["config_path"] == str(cfg_file.resolve())
        assert kwargs["config_dir"] == str(tmp_path.resolve())

    def test_no_selection_forwards_none(self, runner) -> None:
        cfg = _cfg({"brew": {"steps": [["brew", "update"]]}})
        with (
            patch("sysup.config.load_config", return_value=cfg) as mock_load,
            patch("sysup.config.applicable_commands", return_value=[("brew", cfg.commands["brew"])]),
            patch("sysup.runner.Runner.run", return_value=iter([StepResult("brew", True, "ok")])),
        ):
            result = runner.invoke(cli, [])
        assert result.exit_code == 0
        _, kwargs = mock_load.call_args
        assert kwargs["config_path"] is None
        assert kwargs["config_dir"] is None

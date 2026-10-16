from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import click
import pytest
from buvis.pybase.adapters import console
from buvis.pybase.result import FatalError

from sysup.attention import read_state, state_path, write_state
from sysup.cli import cli
from sysup.config import SysupConfig
from sysup.step_result import StepResult

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner, Result


def _cfg(commands: dict[str, dict[str, object]], prime: tuple[str, ...] = ()) -> SysupConfig:
    return SysupConfig.model_validate({"commands": commands, "prime": list(prime)})


class TestSysupCliShape:
    def test_cli_is_a_group_with_status_only(self) -> None:
        assert isinstance(cli, click.Group)
        assert set(cli.commands) == {"status"}

    def test_help_lists_filters(self, runner) -> None:
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


def _attention_cfg(ntfy: dict[str, str] | None = None) -> SysupConfig:
    return SysupConfig.model_validate(
        {"commands": {"brew": {"steps": [["brew"]]}, "helm": {"steps": [["helm"]]}}, "ntfy": ntfy or {}}
    )


def _entry(status: str = "failed", *, notified: bool = False, details: list[str] | None = None) -> dict[str, Any]:
    return {
        "kind": "command",
        "status": status,
        "details": details or ["old failure"],
        "first_seen": "2026-10-13T10:00:00+00:00",
        "last_checked": "2026-10-14T11:00:00+00:00",
        "notified": notified,
    }


def _invoke_run(
    runner: CliRunner, cfg: SysupConfig, results: list[StepResult], args: list[str] | None = None
) -> Result:
    with (
        patch("sysup.config.load_config", return_value=cfg),
        patch("sysup.config.applicable_commands", return_value=list(cfg.commands.items())),
        patch("sysup.runner.Runner.run", return_value=iter(results)),
    ):
        return runner.invoke(cli, args or [])


class TestSysupCliAttention:
    def test_failed_step_prints_summary_writes_state_pushes_once_exits_1(self, runner, mocker) -> None:
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        mocker.patch("platform.node", return_value="test-host")
        result = _invoke_run(runner, cfg, [StepResult("brew", False, "brew failed: boom")])
        assert "attention: 1 unresolved" in result.output
        assert "brew (failed): brew failed: boom" in result.output
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert read_state()["brew"]["notified"] is True
        assert read_state()["brew"]["details"] == ["brew failed: boom"]
        send.assert_called_once_with(
            "https://ntfy.example",
            "sysup",
            "sysup on test-host: 1 need attention",
            "failed brew: brew failed: boom",
            credentials="",
        )

    def test_filtered_run_keeps_and_labels_retained_entries_exits_0(self, runner, mocker) -> None:
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        write_state({"helm": _entry()})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        result = _invoke_run(runner, cfg, [StepResult("brew", True)], ["--only", "brew"])
        assert "helm (failed, not rechecked this run): old failure" in result.output
        assert result.exit_code == 0
        assert send.call_args.args[3] == "failed helm: old failure"
        assert read_state()["helm"]["notified"] is True
        assert runner.invoke(cli, ["status"]).exit_code == 1

    def test_clean_recheck_clears_entry_and_sends_nothing(self, runner, mocker) -> None:
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        write_state({"brew": _entry()})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        blank = mocker.spy(console, "nl")
        result = _invoke_run(runner, cfg, [StepResult("brew", True)])
        assert result.exit_code == 0
        assert "attention:" not in result.output
        assert "notification not sent" not in result.output
        assert read_state() == {}
        send.assert_not_called()
        blank.assert_not_called()

    def test_summary_sorts_entries_joins_details_and_uses_severity_methods(self, runner, mocker) -> None:
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        write_state({"z-token": _entry("expired", details=["first", "second"]), "a-license": _entry("expiring")})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        failure = mocker.spy(console, "failure")
        warning = mocker.spy(console, "warning")
        result = _invoke_run(runner, cfg, [])
        assert result.exit_code == 0
        assert result.output.index("a-license (expiring") < result.output.index("z-token (expired")
        failure.assert_called_once_with("z-token (expired, not rechecked this run): first; second")
        assert warning.call_args_list[0].args == ("attention: 2 unresolved",)
        assert warning.call_args_list[1].args == ("a-license (expiring, not rechecked this run): old failure",)
        assert send.call_args.args[3] == "expiring a-license: old failure\nexpired z-token: first"

    def test_amber_pushes_once_red_every_run_and_title_counts_only_pushed(self, runner, mocker) -> None:
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        write_state(
            {
                "z-red": _entry(),
                "a-amber": _entry("expiring"),
                "b-quiet": _entry("expiring", notified=True),
            }
        )
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        mocker.patch("platform.node", return_value="host")
        first = _invoke_run(runner, cfg, [])
        assert first.exit_code == 0
        assert send.call_args.args[2] == "sysup on host: 2 need attention"
        assert send.call_args.args[3] == "expiring a-amber: old failure\nfailed z-red: old failure"
        second = _invoke_run(runner, cfg, [])
        assert second.exit_code == 0
        assert send.call_count == 2
        assert send.call_args.args[2] == "sysup on host: 1 need attention"
        assert send.call_args.args[3] == "failed z-red: old failure"

    def test_ntfy_not_configured_is_reported_not_fatal(self, runner, mocker) -> None:
        cfg = _attention_cfg()
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = _invoke_run(runner, cfg, [StepResult("brew", False, "boom")])
        assert result.exit_code == 1
        assert "notification not sent: ntfy not configured" in result.output
        assert read_state()["brew"]["notified"] is False
        send.assert_not_called()

    @pytest.mark.parametrize("current_failure,expected_exit", [(True, 1), (False, 0)])
    def test_malformed_ntfy_url_preserves_state_and_exit_code(
        self, runner, mocker, current_failure: bool, expected_exit: int
    ) -> None:
        cfg = _attention_cfg({"url": "not-a-url", "topic": "sysup"})
        write_state({"helm": _entry()})
        opener = mocker.patch("urllib.request.urlopen", autospec=True)
        result = _invoke_run(
            runner,
            cfg,
            [StepResult("brew", not current_failure, "brew failed: boom" if current_failure else "")],
            ["--only", "brew"],
        )
        assert result.exit_code == expected_exit
        assert "notification not sent: ValueError:" in result.output
        assert "Traceback" not in result.output
        assert read_state()["helm"]["notified"] is False
        if current_failure:
            assert read_state()["brew"]["notified"] is False
        opener.assert_not_called()

    def test_failed_notification_retries_without_marking_or_changing_exit(self, runner, mocker) -> None:
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        write_state({"certificate": _entry("expiring")})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, side_effect=["HTTP 403", None])
        first = _invoke_run(runner, cfg, [])
        assert first.exit_code == 0
        assert "notification not sent: HTTP 403" in first.output
        assert read_state()["certificate"]["notified"] is False
        second = _invoke_run(runner, cfg, [])
        assert second.exit_code == 0
        assert read_state()["certificate"]["notified"] is True
        assert send.call_count == 2

    @pytest.mark.parametrize(
        "ntfy,env_url,env_topic,expected_url,expected_topic",
        [
            ({}, "https://env.example", "env-topic", "https://env.example", "env-topic"),
            (
                {"url": "https://config.example"},
                "https://env.example",
                "env-topic",
                "https://config.example",
                "env-topic",
            ),
            ({"topic": "config-topic"}, "https://env.example", "env-topic", "https://env.example", "config-topic"),
            (
                {"url": "https://config.example", "topic": "config-topic"},
                "https://env.example",
                "env-topic",
                "https://config.example",
                "config-topic",
            ),
        ],
    )
    def test_notification_resolves_config_and_independent_environment_fallbacks(
        self, runner, mocker, monkeypatch, ntfy, env_url: str, env_topic: str, expected_url: str, expected_topic: str
    ) -> None:
        monkeypatch.setenv("NTFY_URL", env_url)
        monkeypatch.setenv("NTFY_TOPIC", env_topic)
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        result = _invoke_run(runner, _attention_cfg(ntfy), [StepResult("brew", False, "boom")])
        assert result.exit_code == 1
        assert send.call_args.args[:2] == (expected_url, expected_topic)
        assert read_state()["brew"]["notified"] is True

    def test_credentials_file_is_expanded_and_stripped(self, runner, mocker, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / "credentials").write_text(" user:päss \n")
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup", "credentials_file": "~/credentials"})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        result = _invoke_run(runner, cfg, [StepResult("brew", False, "boom")])
        assert result.exit_code == 1
        assert send.call_args.kwargs["credentials"] == "user:päss"
        assert read_state()["brew"]["notified"] is True

    @pytest.mark.parametrize("error_kind", ["missing", "permission", "unicode"])
    def test_unreadable_credentials_warn_and_leave_notification_pending(
        self, runner, mocker, tmp_path: Path, error_kind: str
    ) -> None:
        credentials = tmp_path / "credentials"
        if error_kind == "unicode":
            credentials.write_bytes(b"\xff")
        elif error_kind == "permission":
            credentials.mkdir()
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup", "credentials_file": str(credentials)})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = _invoke_run(runner, cfg, [StepResult("brew", False, "boom")])
        assert result.exit_code == 1
        assert f"notification not sent: credentials file not readable: {credentials}" in result.output.replace("\n", "")
        assert read_state()["brew"]["notified"] is False
        send.assert_not_called()

    def test_empty_notification_set_reads_no_credentials_or_adapter(self, runner, mocker, tmp_path: Path) -> None:
        cfg = _attention_cfg(
            {"url": "https://ntfy.example", "topic": "sysup", "credentials_file": str(tmp_path / "missing")}
        )
        write_state({"certificate": _entry("expiring", notified=True)})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = _invoke_run(runner, cfg, [])
        assert result.exit_code == 0
        assert "notification not sent" not in result.output
        send.assert_not_called()

    def test_fatal_interruption_folds_writes_and_pushes_nothing(self, runner, mocker) -> None:
        write_state({"helm": _entry()})
        before = state_path().read_bytes()

        def interrupted():
            yield StepResult("brew", False, "boom")
            raise FatalError("fatal interruption")

        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        mocker.patch("sysup.config.load_config", return_value=cfg)
        mocker.patch("sysup.config.applicable_commands", return_value=list(cfg.commands.items()))
        mocker.patch("sysup.runner.Runner.run", return_value=interrupted())
        fold = mocker.patch("sysup.attention.fold_results", autospec=True)
        read = mocker.patch("sysup.attention.read_state", autospec=True)
        write = mocker.patch("sysup.attention.write_state", autospec=True)
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = runner.invoke(cli, [])
        assert result.exit_code == 1
        assert "fatal interruption" in result.output
        assert "attention:" not in result.output
        assert state_path().read_bytes() == before
        fold.assert_not_called()
        read.assert_not_called()
        write.assert_not_called()
        send.assert_not_called()

    def test_state_write_failure_panics_without_traceback(self, runner, mocker) -> None:
        cfg = _attention_cfg()
        mocker.patch("sysup.attention.write_state", side_effect=OSError("state disk full"))
        result = _invoke_run(runner, cfg, [StepResult("brew", True)])
        assert result.exit_code == 1
        assert "state disk full" in result.output
        assert "Traceback" not in result.output


class TestSysupCliStatus:
    def test_status_prints_entries_and_exits_1_on_red(self, runner, mocker) -> None:
        write_state({"z-red": _entry(), "a-amber": _entry("expiring", details=["first", "second"])})
        failure = mocker.spy(console, "failure")
        warning = mocker.spy(console, "warning")
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 1
        warning.assert_called_once_with("a-amber (expiring, checked 2026-10-14T11:00:00+00:00): first; second")
        failure.assert_called_once_with("z-red (failed, checked 2026-10-14T11:00:00+00:00): old failure")
        assert result.output.index("a-amber") < result.output.index("z-red")

    def test_status_runs_nothing_writes_nothing(self, runner, mocker) -> None:
        write_state({"helm": _entry()})
        before = state_path().read_bytes()
        load = mocker.patch("sysup.config.load_config", autospec=True)
        run = mocker.patch("sysup.runner.Runner", autospec=True)
        write = mocker.patch("sysup.attention.write_state", autospec=True)
        fold = mocker.patch("sysup.attention.fold_results", autospec=True)
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 1
        load.assert_not_called()
        run.assert_not_called()
        write.assert_not_called()
        fold.assert_not_called()
        send.assert_not_called()
        assert state_path().read_bytes() == before

    def test_group_options_before_subcommand_run_status_only(self, runner, mocker) -> None:
        load = mocker.patch("sysup.config.load_config", autospec=True)
        run = mocker.patch("sysup.runner.Runner", autospec=True)
        write = mocker.patch("sysup.attention.write_state", autospec=True)
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = runner.invoke(cli, ["--only", "brew", "--tag", "python", "--list", "--dry-run", "status"])
        assert result.exit_code == 0
        assert "nothing needs attention" in result.output
        load.assert_not_called()
        run.assert_not_called()
        write.assert_not_called()
        send.assert_not_called()
        assert not state_path().exists()

    def test_status_options_after_subcommand_are_usage_error(self, runner) -> None:
        result = runner.invoke(cli, ["status", "--only", "brew"])
        assert result.exit_code == 2
        assert "No such option" in result.output
        assert "--only" in result.output

    def test_empty_status_succeeds_without_creating_state(self, runner) -> None:
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "nothing needs attention" in result.output
        assert not state_path().exists()

    def test_amber_status_exits_zero(self, runner) -> None:
        write_state({"certificate": _entry("expiring")})
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "certificate (expiring, checked 2026-10-14T11:00:00+00:00)" in result.output


class TestSysupCliAttentionInspection:
    @pytest.mark.parametrize("option", ["--dry-run", "--list"])
    def test_dry_run_and_list_write_no_state_send_nothing(self, runner, mocker, option: str) -> None:
        write_state({"helm": _entry()})
        before = state_path().read_bytes()
        cfg = _attention_cfg({"url": "https://ntfy.example", "topic": "sysup"})
        mocker.patch("sysup.config.load_config", return_value=cfg)
        mocker.patch("sysup.config.applicable_commands", return_value=list(cfg.commands.items()))
        run = mocker.patch("sysup.runner.Runner.run", return_value=iter([StepResult("brew", True, "would run")]))
        read = mocker.patch("sysup.attention.read_state", autospec=True)
        fold = mocker.patch("sysup.attention.fold_results", autospec=True)
        write = mocker.patch("sysup.attention.write_state", autospec=True)
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = runner.invoke(cli, [option])
        assert result.exit_code == 0
        assert "attention:" not in result.output
        read.assert_not_called()
        fold.assert_not_called()
        write.assert_not_called()
        send.assert_not_called()
        assert state_path().read_bytes() == before
        if option == "--list":
            run.assert_not_called()
        else:
            run.assert_called_once()

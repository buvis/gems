from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from buvis.pybase.result import FatalError

from sysup.attention import read_state, state_path, write_state
from sysup.cli import cli
from sysup.config import SysupConfig
from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from click.testing import CliRunner, Result

_LOG_A = Path("/tmp/sysup-run-1.log")
_LOG_B = Path("/var/log/sysup-2.log")
_NTFY = {"url": "https://ntfy.example", "topic": "sysup"}


def _cfg(ntfy: dict[str, str] | None = None) -> SysupConfig:
    return SysupConfig.model_validate(
        {"commands": {"brew": {"steps": [["brew"]]}, "helm": {"steps": [["helm"]]}}, "ntfy": ntfy or {}}
    )


def _entry(status: str = "failed") -> dict[str, Any]:
    return {
        "kind": "command",
        "status": status,
        "details": ["old failure"],
        "first_seen": "2026-10-13T10:00:00+00:00",
        "last_checked": "2026-10-14T11:00:00+00:00",
        "notified": False,
    }


def _fake_run(
    log_path: Path | None, results: list[StepResult], exc: Exception | None = None
) -> Callable[[Any, Any], Iterator[StepResult]]:
    """Stand-in for Runner.run: opens 'the log' (sets log_path on the instance), yields, maybe raises."""

    def run(self: Any, selected: Any) -> Iterator[StepResult]:
        self.log_path = log_path
        yield from results
        if exc is not None:
            raise exc

    return run


def _invoke(
    runner: CliRunner,
    mocker: Any,
    cfg: SysupConfig,
    run: Callable[[Any, Any], Iterator[StepResult]],
    args: list[str] | None = None,
) -> Result:
    mocker.patch("sysup.config.load_config", return_value=cfg)
    mocker.patch("sysup.config.applicable_commands", return_value=list(cfg.commands.items()))
    mocker.patch("sysup.runner.Runner.run", run)
    return runner.invoke(cli, args or [])


def _flat(result: Result) -> str:
    return result.output.replace("\n", "")


class TestSysupCliFullLogLine:
    @pytest.mark.parametrize("log_path", [_LOG_A, _LOG_B], ids=["tmp", "var"])
    def test_clean_run_prints_one_full_log_line_with_runner_path(self, runner, mocker, log_path: Path) -> None:
        other = _LOG_B if log_path == _LOG_A else _LOG_A
        result = _invoke(runner, mocker, _cfg(), _fake_run(log_path, [StepResult("brew", True, "brew updated")]))
        assert result.exit_code == 0
        assert f"full log: {log_path}" in _flat(result)
        assert str(other) not in _flat(result)
        assert result.output.count("full log:") == 1
        assert result.output.index("brew updated") < result.output.index("full log:")

    def test_amber_run_prints_line_after_summary_and_notification(self, runner, mocker) -> None:
        write_state({"certificate": _entry("expiring")})
        steps = [StepResult("helm", True, "helm: 1 error line", status="warned", command="helm")]
        result = _invoke(runner, mocker, _cfg(), _fake_run(_LOG_A, steps))
        assert result.exit_code == 0
        assert result.output.count("full log:") == 1
        assert f"full log: {_LOG_A}" in _flat(result)
        assert result.output.index("attention: 2 unresolved") < result.output.index("full log:")
        assert result.output.index("notification not sent") < result.output.index("full log:")

    def test_red_run_still_prints_full_log_and_exits_1(self, runner, mocker) -> None:
        steps = [StepResult("helm", True, "helm updated"), StepResult("brew", False, "brew failed: boom")]
        result = _invoke(runner, mocker, _cfg(), _fake_run(_LOG_B, steps))
        assert result.exit_code == 1
        assert result.output.count("full log:") == 1
        assert f"full log: {_LOG_B}" in _flat(result)
        assert read_state()["brew"]["status"] == "failed"

    def test_empty_plan_run_still_prints_full_log(self, runner, mocker) -> None:
        result = _invoke(runner, mocker, _cfg(), _fake_run(_LOG_A, []))
        assert result.exit_code == 0
        assert result.output.count("full log:") == 1
        assert f"full log: {_LOG_A}" in _flat(result)

    def test_no_line_when_runner_opened_no_log(self, runner, mocker) -> None:
        result = _invoke(runner, mocker, _cfg(), _fake_run(None, [StepResult("brew", True, "brew updated")]))
        assert result.exit_code == 0
        assert "brew updated" in result.output
        assert "full log" not in result.output
        assert "None" not in result.output

    def test_state_write_failure_prints_no_full_log_line(self, runner, mocker) -> None:
        mocker.patch("sysup.attention.write_state", side_effect=OSError("state disk full"))
        result = _invoke(runner, mocker, _cfg(), _fake_run(_LOG_A, [StepResult("brew", True, "brew updated")]))
        assert result.exit_code == 1
        assert "state disk full" in result.output
        assert "full log:" not in result.output
        assert "Traceback" not in result.output


class TestSysupCliNoLogForInspection:
    def test_dry_run_prints_no_full_log_line_even_if_path_set(self, runner, mocker) -> None:
        result = _invoke(
            runner, mocker, _cfg(), _fake_run(_LOG_A, [StepResult("brew", True, "would run")]), ["--dry-run"]
        )
        assert result.exit_code == 0
        assert "would run" in result.output
        assert "full log" not in result.output
        assert str(_LOG_A) not in result.output

    def test_list_constructs_no_runner_and_prints_no_full_log(self, runner, mocker) -> None:
        cfg = _cfg()
        mocker.patch("sysup.config.load_config", return_value=cfg)
        mocker.patch("sysup.config.applicable_commands", return_value=list(cfg.commands.items()))
        runner_cls = mocker.patch("sysup.runner.Runner", autospec=True)
        result = runner.invoke(cli, ["--list"])
        assert result.exit_code == 0
        assert "brew" in result.output
        assert "full log" not in result.output
        runner_cls.assert_not_called()

    def test_refresh_opens_no_run_log_and_prints_no_full_log(self, runner, mocker) -> None:
        from datetime import datetime, timezone

        cfg = SysupConfig.model_validate(
            {
                "commands": {},
                "expiry": {
                    "gh-agent": {
                        "use": "gh-token-expiry",
                        "with": {"config_dir": "~/.config/gh-agent", "probe": "repos/x/y"},
                        "refresh": {"instructions": "paste it", "commands": [{"argv": ["true"], "stdin": "secret"}]},
                    }
                },
            }
        )
        mocker.patch("sysup.cli._is_tty", return_value=True)
        mocker.patch("sysup.config.load_config", return_value=cfg)
        mocker.patch("getpass.getpass", return_value="tok")
        mocker.patch(
            "sysup.refresh.subprocess.run",
            return_value=__import__("subprocess").CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )
        cap = mocker.MagicMock()
        cap.expires_at.return_value = datetime(2030, 1, 1, tzinfo=timezone.utc)
        mocker.patch.dict("sysup.runner.EXPIRY_CAPABILITIES", {"gh-token-expiry": cap})
        run = mocker.patch("sysup.runner.Runner.run", side_effect=AssertionError("refresh must not run updates"))
        result = runner.invoke(cli, ["refresh", "gh-agent"], input="\n")
        assert result.exit_code == 0
        assert "full log" not in result.output
        run.assert_not_called()

    def test_config_fatal_error_prints_no_full_log_and_builds_no_runner(self, runner, mocker) -> None:
        mocker.patch("sysup.config.load_config", side_effect=FatalError("bad config"))
        runner_cls = mocker.patch("sysup.runner.Runner", autospec=True)
        result = runner.invoke(cli, [])
        assert result.exit_code == 1
        assert "bad config" in result.output
        assert "full log" not in result.output
        runner_cls.assert_not_called()


class TestSysupCliLogErrors:
    @pytest.mark.parametrize(
        "log_path,steps,message",
        [
            (None, [], "could not open run log: Permission denied"),
            (_LOG_A, [StepResult("brew", False, "brew failed: boom")], f"run log incomplete: {_LOG_A}: disk full"),
            (_LOG_B, [StepResult("brew", True, "brew updated")], "run log write failed: No space left on device"),
        ],
        ids=["open-fails", "path-in-message", "path-not-in-message"],
    )
    def test_log_fatal_error_panics_without_state_notify_or_completed_log_claim(
        self, runner, mocker, log_path: Path | None, steps: list[StepResult], message: str
    ) -> None:
        write_state({"helm": _entry()})
        before = state_path().read_bytes()
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        write = mocker.patch("sysup.attention.write_state", autospec=True)
        result = _invoke(runner, mocker, _cfg(_NTFY), _fake_run(log_path, steps, FatalError(message)))
        assert result.exit_code == 1
        assert message in _flat(result)
        assert "Traceback" not in result.output
        assert "full log" not in result.output
        assert "attention:" not in result.output
        assert state_path().read_bytes() == before
        write.assert_not_called()
        send.assert_not_called()
        if log_path is not None:
            # A retained path may appear only inside the controlled error itself.
            assert _flat(result).count(str(log_path)) == message.count(str(log_path))

    def test_log_fatal_error_after_successful_steps_keeps_their_lines(self, runner, mocker) -> None:
        steps = [StepResult("helm", True, "helm updated"), StepResult("brew", True, "brew updated")]
        result = _invoke(runner, mocker, _cfg(), _fake_run(_LOG_A, steps, FatalError("run log write failed: EIO")))
        assert result.exit_code == 1
        assert "helm updated" in result.output
        assert "brew updated" in result.output
        assert result.output.index("brew updated") < result.output.index("run log write failed: EIO")
        assert "full log" not in result.output


class TestSysupCliNonterminalConsole:
    def test_real_console_on_pipe_emits_no_escapes_and_keeps_result_lines(self, runner, mocker, monkeypatch) -> None:
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("TTY_COMPATIBLE", raising=False)
        steps = [
            StepResult("helm", True, "helm updated"),
            StepResult("brew", False, "brew failed: boom"),
        ]
        result = _invoke(runner, mocker, _cfg(), _fake_run(_LOG_A, steps))
        assert result.exit_code == 1
        assert "\x1b" not in result.output
        for line in ("helm updated", "brew failed: boom", "attention: 1 unresolved", f"full log: {_LOG_A}"):
            assert line in _flat(result)

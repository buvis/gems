from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from buvis.pybase.adapters import console

from sysup.attention import read_state, write_state
from sysup.cli import cli
from sysup.config import SysupConfig
from sysup.step_result import StepResult

if TYPE_CHECKING:
    from click.testing import CliRunner, Result


def _cfg(ntfy: dict[str, str] | None = None) -> SysupConfig:
    return SysupConfig.model_validate(
        {"commands": {"brew": {"steps": [["brew"]]}, "helm": {"steps": [["helm"]]}}, "ntfy": ntfy or {}}
    )


_NTFY = {"url": "https://ntfy.example", "topic": "sysup"}


def _warned(label: str, message: str) -> StepResult:
    return StepResult(label, True, message, status="warned", command=label)


def _entry(status: str, details: list[str], *, notified: bool = False) -> dict[str, Any]:
    return {
        "kind": "command",
        "status": status,
        "details": details,
        "first_seen": "2026-10-13T10:00:00+00:00",
        "last_checked": "2026-10-14T11:00:00+00:00",
        "notified": notified,
    }


def _invoke(runner: CliRunner, cfg: SysupConfig, results: list[StepResult], args: list[str] | None = None) -> Result:
    with (
        patch("sysup.config.load_config", return_value=cfg),
        patch("sysup.config.applicable_commands", return_value=list(cfg.commands.items())),
        patch("sysup.runner.Runner.run", return_value=iter(results)),
    ):
        return runner.invoke(cli, args or [])


class TestSysupCliWarnedRendering:
    def test_warned_step_renders_as_warning_not_success_or_failure(self, runner, mocker) -> None:
        warning = mocker.spy(console, "warning")
        success = mocker.spy(console, "success")
        failure = mocker.spy(console, "failure")
        result = _invoke(
            runner,
            _cfg(),
            [_warned("brew", "brew: 2 error lines in output"), StepResult("helm", True, "helm updated")],
        )
        assert result.exit_code == 0
        assert "Traceback" not in result.output
        assert ("brew: 2 error lines in output",) in [c.args for c in warning.call_args_list]
        assert ("brew: 2 error lines in output",) not in [c.args for c in success.call_args_list]
        assert ("brew: 2 error lines in output",) not in [c.args for c in failure.call_args_list]
        assert ("helm updated",) in [c.args for c in success.call_args_list]
        assert ("helm updated",) not in [c.args for c in warning.call_args_list]

    def test_warned_step_without_message_falls_back_to_label(self, runner, mocker) -> None:
        warning = mocker.spy(console, "warning")
        result = _invoke(runner, _cfg(), [_warned("helm", "")])
        assert result.exit_code == 0
        assert ("helm warned",) in [c.args for c in warning.call_args_list]
        assert "helm updated" not in result.output


class TestSysupCliWarnedAttention:
    def test_warned_step_persists_amber_entry_and_exits_0(self, runner, mocker) -> None:
        mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        result = _invoke(runner, _cfg(_NTFY), [_warned("helm", "helm: deprecated chart"), StepResult("brew", True)])
        assert result.exit_code == 0
        state = read_state()
        assert set(state) == {"helm"}
        assert state["helm"]["status"] == "warned"
        assert state["helm"]["details"] == ["helm: deprecated chart"]
        assert "attention: 1 unresolved" in result.output
        assert "helm (warned): helm: deprecated chart" in result.output

    def test_warned_entry_notifies_once_across_runs(self, runner, mocker) -> None:
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        mocker.patch("platform.node", return_value="box-7")
        first = _invoke(runner, _cfg(_NTFY), [_warned("brew", "brew: 3 error lines")])
        assert first.exit_code == 0
        assert send.call_count == 1
        assert send.call_args.args[2] == "sysup on box-7: 1 need attention"
        assert send.call_args.args[3] == "warned brew: brew: 3 error lines"
        assert read_state()["brew"]["notified"] is True
        second = _invoke(runner, _cfg(_NTFY), [_warned("brew", "brew: 3 error lines")])
        assert second.exit_code == 0
        assert send.call_count == 1
        assert read_state()["brew"]["notified"] is True

    def test_clean_recheck_clears_warned_entry(self, runner, mocker) -> None:
        write_state({"brew": _entry("warned", ["brew: 1 error line"], notified=True)})
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = _invoke(runner, _cfg(_NTFY), [StepResult("brew", True, "brew updated")])
        assert result.exit_code == 0
        assert read_state() == {}
        assert "attention:" not in result.output
        send.assert_not_called()

    def test_ntfy_title_counts_and_details_every_pushed_entry(self, runner, mocker) -> None:
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True, return_value=None)
        mocker.patch("platform.node", return_value="host-a")
        result = _invoke(
            runner,
            _cfg(_NTFY),
            [_warned("helm", "helm: lint warning"), StepResult("brew", False, "brew failed: boom")],
        )
        assert result.exit_code == 1
        assert send.call_count == 1
        assert send.call_args.args[2] == "sysup on host-a: 2 need attention"
        assert send.call_args.args[3] == "failed brew: brew failed: boom\nwarned helm: helm: lint warning"

    def test_no_steps_and_no_state_sends_nothing_and_exits_0(self, runner, mocker) -> None:
        send = mocker.patch("buvis.pybase.adapters.ntfy.send_ntfy", autospec=True)
        result = _invoke(runner, _cfg(_NTFY), [])
        assert result.exit_code == 0
        assert read_state() == {}
        send.assert_not_called()


class TestSysupCliRedExits:
    def test_failed_step_exits_1_even_beside_warned(self, runner) -> None:
        result = _invoke(runner, _cfg(), [_warned("helm", "helm: lint"), StepResult("brew", False, "brew failed: x")])
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert read_state()["brew"]["status"] == "failed"
        assert read_state()["helm"]["status"] == "warned"

    def test_only_warned_steps_exit_0(self, runner) -> None:
        result = _invoke(runner, _cfg(), [_warned("helm", "helm: lint"), _warned("brew", "brew: lint")])
        assert result.exit_code == 0
        assert {name: entry["status"] for name, entry in read_state().items()} == {"brew": "warned", "helm": "warned"}

from __future__ import annotations

import subprocess

import pytest
from buvis.pybase.result import FatalError

from sysup.config import SysupCommand
from sysup.runner import Runner
from sysup.step_result import StepResult


def _cmd(**kwargs: object) -> SysupCommand:
    return SysupCommand.model_validate(kwargs)


def _cfg(prime: tuple[str, ...] = ()) -> object:
    from sysup.config import SysupConfig

    return SysupConfig.model_validate({"prime": list(prime)})


class TestRunnerRunEntries:
    @staticmethod
    def _ok(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)

    def test_run_entry_all_steps_succeed_single_result(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=self._ok())
        cmd = _cmd(steps=[["brew", "update"], ["brew", "upgrade"], ["brew", "cleanup"]])

        steps = list(Runner(_cfg()).run([("brew", cmd)]))

        assert len(steps) == 1
        assert steps[0].label == "brew"
        assert steps[0].success is True

    def test_run_entry_aborts_on_first_failure(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mock_run = mocker.patch("sysup.runner.subprocess.run")
        mock_run.side_effect = [
            self._ok(returncode=1, stderr="boom"),
            self._ok(),
        ]
        cmd = _cmd(steps=[["brew", "update"], ["brew", "upgrade"]])

        steps = list(Runner(_cfg()).run([("brew", cmd)]))

        assert len(steps) == 1
        assert steps[0].success is False
        assert "boom" in steps[0].message
        # cleanup/upgrade never ran: only the first step spawned.
        assert mock_run.call_count == 1

    def test_continue_on_error_keeps_going(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mock_run = mocker.patch("sysup.runner.subprocess.run")
        mock_run.side_effect = [self._ok(returncode=1, stderr="x"), self._ok()]
        cmd = _cmd(continue_on_error=True, steps=[["a"], ["b"]])

        steps = list(Runner(_cfg()).run([("multi", cmd)]))

        assert mock_run.call_count == 2
        assert steps[0].success is False
        assert steps[1].success is True

    def test_interactive_inherits_stdio_exit_code_only(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mock_run = mocker.patch("sysup.runner.subprocess.run", return_value=self._ok())
        cmd = _cmd(interactive=True, steps=[["npm-check", "-gu"]])

        steps = list(Runner(_cfg()).run([("npm-check", cmd)]))

        assert steps[0].success is True
        # interactive: no capture_output/text kwargs
        call = mock_run.call_args_list[0]
        assert "capture_output" not in call.kwargs
        assert call.kwargs.get("check") is False

    def test_interactive_failure_reports_exit_code(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=self._ok(returncode=3))
        cmd = _cmd(interactive=True, steps=[["npm-check", "-gu"]])

        steps = list(Runner(_cfg()).run([("npm-check", cmd)]))

        assert steps[0].success is False
        assert "exit code 3" in steps[0].message

    def test_missing_binary_is_reported_not_run(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", return_value=None)
        mock_run = mocker.patch("sysup.runner.subprocess.run")
        cmd = _cmd(steps=[["ghost"]])

        steps = list(Runner(_cfg()).run([("ghost", cmd)]))

        assert steps[0].success is False
        assert "not found" in steps[0].message
        assert mock_run.call_count == 0

    def test_per_step_which_called_each_step(self, mocker) -> None:
        which = mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=self._ok())
        cmd = _cmd(continue_on_error=True, steps=[["a"], ["b"], ["c"]])

        list(Runner(_cfg()).run([("multi", cmd)]))

        assert which.call_count == 3


class TestRunnerUseEntries:
    def test_use_entry_yields_capability_steps(self, mocker) -> None:
        cap = mocker.MagicMock()
        cap.run.return_value = iter([StepResult("helm repos", success=True)])
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"helm-repo-update": cap})
        cmd = _cmd(use="helm-repo-update")

        steps = list(Runner(_cfg()).run([("helm", cmd)]))

        assert steps[0].label == "helm repos"
        assert steps[0].success is True

    def test_use_passes_with_inputs(self, mocker) -> None:
        cap = mocker.MagicMock()
        cap.run.return_value = iter([StepResult("mason", success=True)])
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"nvim-mason": cap})
        cmd = _cmd(use="nvim-mason", **{"with": {"timeout": 42}})

        list(Runner(_cfg()).run([("nvim", cmd)]))

        cap.run.assert_called_once_with(timeout=42)

    def test_capability_unexpected_raise_becomes_failed_step(self, mocker) -> None:
        cap = mocker.MagicMock()
        cap.run.side_effect = RuntimeError("kaboom")
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        cmd = _cmd(use="pip-outdated")

        steps = list(Runner(_cfg()).run([("pip", cmd)]))

        assert steps[0].success is False
        assert "kaboom" in steps[0].message

    def test_capability_fatal_error_propagates(self, mocker) -> None:
        cap = mocker.MagicMock()
        cap.run.side_effect = FatalError("nvim not found")
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"nvim-mason": cap})
        cmd = _cmd(use="nvim-mason")

        with pytest.raises(FatalError, match="nvim not found"):
            list(Runner(_cfg()).run([("nvim", cmd)]))


def _ok() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


class TestRunnerPrime:
    def test_prime_runs_before_commands(self, mocker) -> None:
        order: list[str] = []
        from sysup.capabilities.sudo import SudoPrime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        prime_cap = mocker.MagicMock(spec=SudoPrime)
        prime_cap.prime.side_effect = lambda: order.append("primed") or (lambda: None)
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch(
            "sysup.runner.subprocess.run",
            side_effect=lambda *a, **k: (
                order.append("step") or subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            ),
        )
        cmd = _cmd(steps=[["brew", "update"]], sudo=True)

        list(Runner(_cfg(prime=("sudo-prime",))).run([("brew", cmd)]))

        assert order[0] == "primed"
        assert "step" in order

    def test_stop_called_in_finally_on_keyboardinterrupt(self, mocker) -> None:
        stopped: list[bool] = []
        from sysup.capabilities.sudo import SudoPrime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        prime_cap = mocker.MagicMock(spec=SudoPrime)
        prime_cap.prime.return_value = lambda: stopped.append(True)
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", side_effect=KeyboardInterrupt())
        cmd = _cmd(steps=[["brew", "update"]], sudo=True)

        with pytest.raises(KeyboardInterrupt):
            list(Runner(_cfg(prime=("sudo-prime",))).run([("brew", cmd)]))

        assert stopped == [True]

    def test_no_tty_skips_prime(self, mocker) -> None:
        from sysup.capabilities.sudo import SudoPrime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=False)
        prime_cap = mocker.MagicMock(spec=SudoPrime)
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_ok())
        cmd = _cmd(steps=[["brew", "update"]], sudo=True)

        list(Runner(_cfg(prime=("sudo-prime",))).run([("brew", cmd)]))

        assert prime_cap.prime.call_count == 0

    def test_no_sudo_needing_command_skips_prime(self, mocker) -> None:
        from sysup.capabilities.sudo import SudoPrime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        prime_cap = mocker.MagicMock(spec=SudoPrime)
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_ok())
        cmd = _cmd(steps=[["brew", "update"]])

        list(Runner(_cfg(prime=("sudo-prime",))).run([("brew", cmd)]))

        assert prime_cap.prime.call_count == 0

    def test_sudo_argv_first_step_triggers_prime(self, mocker) -> None:
        from sysup.capabilities.sudo import SudoPrime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        prime_cap = mocker.MagicMock(spec=SudoPrime)
        prime_cap.prime.return_value = lambda: None
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_ok())
        cmd = _cmd(steps=[["sudo", "apt", "update"]])

        list(Runner(_cfg(prime=("sudo-prime",))).run([("apt", cmd)]))

        assert prime_cap.prime.call_count == 1


class TestRunnerLogWiring:
    def test_run_opens_and_closes_log_with_plan_names(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_ok())
        cmd = _cmd(steps=[["brew", "update"]])

        runner = Runner(_cfg())
        list(runner.run([("brew", cmd)]))

        assert runner.log_path is not None
        assert runner.log_path.exists()
        assert "plan: brew" in runner.log_path.read_text()

    def test_dry_run_creates_no_log(self, mocker) -> None:
        from sysup import runlog

        cmd = _cmd(steps=[["brew", "update"]])
        runner = Runner(_cfg(), dry_run=True)
        list(runner.run([("brew", cmd)]))

        assert runner.log_path is None
        assert not runlog.logs_dir().exists()

    def test_log_open_failure_propagates_as_fatal(self, mocker) -> None:
        mocker.patch("sysup.runner.runlog.open_run_log", side_effect=FatalError("could not create run log"))
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_ok())
        cmd = _cmd(steps=[["brew", "update"]])

        with pytest.raises(FatalError, match="could not create run log"):
            list(Runner(_cfg()).run([("brew", cmd)]))

    def test_close_called_even_when_entry_raises(self, mocker) -> None:
        close = mocker.patch("sysup.runner.runlog.close")
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", side_effect=KeyboardInterrupt())
        cmd = _cmd(steps=[["brew", "update"]])

        with pytest.raises(KeyboardInterrupt):
            list(Runner(_cfg()).run([("brew", cmd)]))

        assert close.called


class TestShouldPrime:
    def test_tty_and_sudo_flag(self, mocker) -> None:
        from sysup.runner import _should_prime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        assert _should_prime([("brew", _cmd(steps=[["brew", "update"]], sudo=True))]) is True

    def test_tty_and_sudo_argv(self, mocker) -> None:
        from sysup.runner import _should_prime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        assert _should_prime([("apt", _cmd(steps=[["sudo", "apt", "update"]]))]) is True

    def test_no_tty_is_false(self, mocker) -> None:
        from sysup.runner import _should_prime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=False)
        assert _should_prime([("brew", _cmd(steps=[["brew", "update"]], sudo=True))]) is False

    def test_no_sudo_needing_entry_is_false(self, mocker) -> None:
        from sysup.runner import _should_prime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        assert _should_prime([("brew", _cmd(steps=[["brew", "update"]]))]) is False

    def test_checks_every_step_not_only_first(self, mocker) -> None:
        from sysup.runner import _should_prime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        cmd = _cmd(steps=[["brew", "update"], ["sudo", "something"]])
        assert _should_prime([("brew", cmd)]) is True


class TestRunnerStatusContexts:
    def test_captured_step_wrapped_in_status(self, mocker) -> None:
        status = mocker.patch("sysup.runner.console.status")
        status.return_value.__enter__ = mocker.Mock(return_value=None)
        status.return_value.__exit__ = mocker.Mock(return_value=False)
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_ok())
        cmd = _cmd(steps=[["brew", "update"]])

        list(Runner(_cfg()).run([("brew", cmd)]))

        status.assert_any_call("brew: brew update")

    def test_interactive_step_not_wrapped_in_status(self, mocker) -> None:
        status = mocker.patch("sysup.runner.console.status")
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_ok())
        cmd = _cmd(interactive=True, steps=[["npm-check", "-gu"]])

        list(Runner(_cfg()).run([("npm-check", cmd)]))

        assert status.call_count == 0

    def test_use_entry_wrapped_in_status(self, mocker) -> None:
        status = mocker.patch("sysup.runner.console.status")
        status.return_value.__enter__ = mocker.Mock(return_value=None)
        status.return_value.__exit__ = mocker.Mock(return_value=False)
        cap = mocker.MagicMock()
        cap.run.return_value = iter([StepResult("helm repos", success=True)])
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"helm-repo-update": cap})
        cmd = _cmd(use="helm-repo-update")

        list(Runner(_cfg()).run([("helm", cmd)]))

        status.assert_any_call("helm: helm-repo-update")


class TestRunnerTimeout:
    def test_captured_timeout_reports_no_exit_code_and_partial_output(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        exc = subprocess.TimeoutExpired(cmd=["mise"], timeout=30, output=b"partial-out", stderr=b"partial-err")
        mocker.patch("sysup.runner.subprocess.run", side_effect=exc)
        cmd = _cmd(steps=[["mise", "self-update"]], timeout=30)

        outcomes = []
        runner = Runner(_cfg())
        outcome = runner._run_argv("mise", ["mise", "self-update"], cmd)
        outcomes.append(outcome)

        assert outcomes[0].timed_out is True
        assert outcomes[0].exit_code is None
        assert outcomes[0].timeout_s == 30
        assert outcomes[0].stdout == "partial-out"
        assert outcomes[0].stderr == "partial-err"
        assert outcomes[0].result.success is False
        assert "timed out after 30s" in outcomes[0].result.message

    def test_interactive_timeout_reports_no_exit_code(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        exc = subprocess.TimeoutExpired(cmd=["npm-check"], timeout=10)
        mocker.patch("sysup.runner.subprocess.run", side_effect=exc)
        cmd = _cmd(interactive=True, steps=[["npm-check", "-gu"]], timeout=10)

        outcome = Runner(_cfg())._run_argv("npm-check", ["npm-check", "-gu"], cmd)

        assert outcome.timed_out is True
        assert outcome.exit_code is None
        assert outcome.result.success is False

    def test_no_timeout_configured_outcome_carries_exit_code(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch(
            "sysup.runner.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="out", stderr=""),
        )
        cmd = _cmd(steps=[["brew", "update"]])

        outcome = Runner(_cfg())._run_argv("brew", ["brew", "update"], cmd)

        assert outcome.timed_out is False
        assert outcome.exit_code == 0
        assert outcome.stdout == "out"


class TestRunnerDryRun:
    def test_dry_run_spawns_nothing_and_does_not_prime(self, mocker) -> None:
        from sysup.capabilities.sudo import SudoPrime

        prime_cap = mocker.MagicMock(spec=SudoPrime)
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mock_run = mocker.patch("sysup.runner.subprocess.run")
        mock_which = mocker.patch("sysup.runner.shutil.which")
        cmd = _cmd(steps=[["brew", "update"]])

        steps = list(Runner(_cfg(prime=("sudo-prime",)), dry_run=True).run([("brew", cmd)]))

        assert mock_run.call_count == 0
        assert mock_which.call_count == 0
        assert prime_cap.prime.call_count == 0
        assert steps[0].success is True
        assert "would run" in steps[0].message

    def test_dry_run_use_entry_reports_without_calling(self, mocker) -> None:
        cap = mocker.MagicMock()
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        cmd = _cmd(use="pip-outdated")

        steps = list(Runner(_cfg(), dry_run=True).run([("pip", cmd)]))

        assert cap.run.call_count == 0
        assert steps[0].success is True
        assert "would run capability" in steps[0].message


class TestRunnerCommandStamping:
    def test_results_carry_command_name(self, mocker) -> None:
        mocker.patch("sysup.runner.shutil.which", return_value="/bin/tool")
        mocker.patch(
            "sysup.runner.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        )
        steps = list(Runner(_cfg()).run([("entry-name", _cmd(steps=[["tool"]]))]))
        assert steps == [StepResult("entry-name", True, command="entry-name")]

    def test_capability_results_are_restamped_with_command(self, mocker) -> None:
        original = StepResult("pip (3.12)", False, "numpy failed", command="other")
        cap = mocker.MagicMock()
        cap.run.return_value = iter([original, StepResult("pip (3.13)", True)])
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        steps = list(Runner(_cfg()).run([("pip", _cmd(use="pip-outdated"))]))
        assert steps[0].label == "pip (3.12)"
        assert steps[0].command == "pip"
        assert steps[1].command == "pip"
        assert original.command == "other"

    def test_capability_generator_error_is_caught_inside_iteration(self, mocker) -> None:
        def generate():
            yield StepResult("pip (3.12)", True)
            raise RuntimeError("iterator failed")

        cap = mocker.MagicMock()
        cap.run.return_value = generate()
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        steps = list(Runner(_cfg()).run([("pip", _cmd(use="pip-outdated"))]))
        assert steps == [
            StepResult("pip (3.12)", True, command="pip"),
            StepResult("pip", False, "pip failed: iterator failed", command="pip"),
        ]

    @pytest.mark.parametrize("error", [FatalError("fatal iterator"), KeyboardInterrupt()])
    def test_capability_generator_fatal_or_interrupt_propagates(self, mocker, error) -> None:
        def generate():
            yield StepResult("pip (3.12)", True)
            raise error

        cap = mocker.MagicMock()
        cap.run.return_value = generate()
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        with pytest.raises(type(error)):
            list(Runner(_cfg()).run([("pip", _cmd(use="pip-outdated"))]))

    @pytest.mark.parametrize(
        "options,returncode,binary",
        [
            ({"steps": [["tool"]]}, 0, "/bin/tool"),
            ({"steps": [["tool"]]}, 1, "/bin/tool"),
            ({"steps": [["tool"]]}, 0, None),
            ({"steps": [[]]}, 0, "/bin/tool"),
            ({"steps": [["tool"]], "interactive": True}, 0, "/bin/tool"),
            ({"steps": [["tool"]], "interactive": True}, 3, "/bin/tool"),
            ({"steps": [["tool"], ["tool"]], "continue_on_error": True}, 0, "/bin/tool"),
            ({"steps": [["tool"], ["tool"]], "continue_on_error": True}, 1, "/bin/tool"),
        ],
    )
    def test_own_results_stamp_every_run_success_and_failure(self, mocker, options, returncode: int, binary) -> None:
        mocker.patch("sysup.runner.shutil.which", return_value=binary)
        mocker.patch(
            "sysup.runner.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr="boom"),
        )
        steps = list(Runner(_cfg()).run([("entry-name", _cmd(**options))]))
        assert steps
        assert all(step.command == "entry-name" for step in steps)

    @pytest.mark.parametrize("options", [{"steps": [["tool"]]}, {"use": "pip-outdated"}])
    def test_dry_run_results_stamp_command(self, options) -> None:
        steps = list(Runner(_cfg(), dry_run=True).run([("entry-name", _cmd(**options))]))
        assert steps[0].command == "entry-name"

    def test_capability_call_error_is_stamped(self, mocker) -> None:
        cap = mocker.MagicMock()
        cap.run.side_effect = RuntimeError("boom")
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        steps = list(Runner(_cfg()).run([("pip", _cmd(use="pip-outdated"))]))
        assert steps[0].command == "pip"

    def test_missing_capability_result_is_stamped(self) -> None:
        steps = list(Runner(_cfg())._run_use("entry-name", _cmd(steps=[["tool"]])))
        assert steps[0].command == "entry-name"
        assert steps[0].status == "failed"


def _expiry_cfg(items: dict[str, dict[str, object]], commands: dict[str, dict[str, object]] | None = None) -> object:
    from sysup.config import SysupConfig

    return SysupConfig.model_validate({"expiry": items, "commands": commands or {}})


class TestClassifyExpiry:
    def test_header_date_maps_to_ok_expiring_expired_around_warn_days(self) -> None:
        from datetime import datetime, timedelta, timezone

        from sysup.capabilities.gh_token import parse_expiration
        from sysup.runner import classify_expiry

        now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)

        def _at(days: int) -> datetime:
            moment = now + timedelta(days=days)
            return parse_expiration(moment.strftime("%Y-%m-%d %H:%M:%S UTC"))

        assert classify_expiry("x", _at(40), 30, now).status == "ok"
        assert classify_expiry("x", _at(30), 30, now).status == "expiring"
        assert classify_expiry("x", _at(1), 30, now).status == "expiring"
        assert classify_expiry("x", _at(-1), 30, now).status == "expired"
        assert classify_expiry("x", now, 30, now).status == "expired"

    def test_unknown_outcome_maps_to_unknown(self) -> None:
        from datetime import datetime, timezone

        from sysup.runner import classify_expiry

        now = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)
        step = classify_expiry("gh-agent", "grant broken: ...", 30, now)
        assert step.status == "unknown"
        assert step.kind == "item"
        assert step.success is False


class TestRunnerItems:
    def _ok(self) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def test_items_are_checked_before_prime_and_commands(self, mocker) -> None:
        from datetime import datetime, timezone

        from sysup.capabilities.sudo import SudoPrime

        mocker.patch("sysup.runner.sys.stdin.isatty", return_value=True)
        order: list[str] = []
        cap = mocker.MagicMock()
        cap.expires_at.side_effect = lambda **_: order.append("item") or datetime(2030, 1, 1, tzinfo=timezone.utc)
        cap.warn_days = 30
        mocker.patch.dict("sysup.runner.EXPIRY_CAPABILITIES", {"x509-expiry": cap})
        prime_cap = mocker.MagicMock(spec=SudoPrime)
        prime_cap.prime.side_effect = lambda: order.append("primed") or (lambda: None)
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch(
            "sysup.runner.subprocess.run",
            side_effect=lambda *a, **k: order.append("step") or self._ok(),
        )
        cfg = _expiry_cfg(
            {"cert": {"use": "x509-expiry", "with": {"path": "/c.pem"}}},
            {"brew": {"steps": [["brew", "update"]], "sudo": True}},
        )
        cfg = cfg.model_copy(update={"prime": ("sudo-prime",)})

        list(Runner(cfg).run([("brew", cfg.commands["brew"])]))

        assert order == ["item", "primed", "step"]

    def test_dry_run_skips_item_probes(self, mocker) -> None:
        cap = mocker.MagicMock()
        mocker.patch.dict("sysup.runner.EXPIRY_CAPABILITIES", {"x509-expiry": cap})
        cfg = _expiry_cfg({"cert": {"use": "x509-expiry", "with": {"path": "/c.pem"}}})

        steps = list(Runner(cfg, dry_run=True).run([]))

        assert steps == []
        assert cap.expires_at.call_count == 0

    def test_capability_exception_becomes_unknown(self, mocker) -> None:
        cap = mocker.MagicMock()
        cap.expires_at.side_effect = RuntimeError("boom")
        mocker.patch.dict("sysup.runner.EXPIRY_CAPABILITIES", {"x509-expiry": cap})
        cfg = _expiry_cfg({"cert": {"use": "x509-expiry", "with": {"path": "/c.pem"}}})

        steps = list(Runner(cfg).run([]))

        assert len(steps) == 1
        assert steps[0].status == "unknown"
        assert "RuntimeError: boom" in steps[0].message

    def test_needs_expired_item_skips_command_with_refresh_hint(self, mocker) -> None:
        from datetime import datetime, timezone

        cap = mocker.MagicMock()
        cap.expires_at.return_value = datetime(2020, 1, 1, tzinfo=timezone.utc)
        mocker.patch.dict("sysup.runner.EXPIRY_CAPABILITIES", {"gh-token-expiry": cap})
        run = mocker.patch("sysup.runner.subprocess.run")
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        cfg = _expiry_cfg(
            {"gh-agent": {"use": "gh-token-expiry", "with": {"config_dir": "/c", "probe": "repos/x/y"}}},
            {"brew": {"steps": [["brew", "update"]], "needs": ["gh-agent"]}},
        )

        steps = list(Runner(cfg).run([("brew", cfg.commands["brew"])]))

        skip = next(s for s in steps if s.command == "brew")
        assert skip.success is False
        assert skip.message == "brew skipped: gh-agent is expired; run: sysup refresh gh-agent"
        assert run.call_count == 0

    def test_needs_unknown_item_skips_command(self, mocker) -> None:
        cap = mocker.MagicMock()
        cap.expires_at.return_value = "grant broken: ..."
        mocker.patch.dict("sysup.runner.EXPIRY_CAPABILITIES", {"gh-token-expiry": cap})
        run = mocker.patch("sysup.runner.subprocess.run")
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        cfg = _expiry_cfg(
            {"gh-agent": {"use": "gh-token-expiry", "with": {"config_dir": "/c", "probe": "repos/x/y"}}},
            {"brew": {"steps": [["brew", "update"]], "needs": ["gh-agent"]}},
        )

        steps = list(Runner(cfg).run([("brew", cfg.commands["brew"])]))

        skip = next(s for s in steps if s.command == "brew")
        assert "gh-agent is unknown" in skip.message
        assert run.call_count == 0

    def test_needs_ok_or_expiring_item_runs_command(self, mocker) -> None:
        from datetime import datetime, timedelta, timezone

        cap = mocker.MagicMock()
        cap.expires_at.return_value = datetime.now(timezone.utc) + timedelta(days=10)
        mocker.patch.dict("sysup.runner.EXPIRY_CAPABILITIES", {"gh-token-expiry": cap})
        run = mocker.patch("sysup.runner.subprocess.run", return_value=self._ok())
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        cfg = _expiry_cfg(
            {"gh-agent": {"use": "gh-token-expiry", "with": {"config_dir": "/c", "probe": "repos/x/y"}}},
            {"brew": {"steps": [["brew", "update"]], "needs": ["gh-agent"]}},
        )

        steps = list(Runner(cfg).run([("brew", cfg.commands["brew"])]))

        brew = next(s for s in steps if s.command == "brew")
        assert brew.success is True
        assert run.call_count == 1

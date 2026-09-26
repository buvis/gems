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


class TestRunnerPrime:
    def test_prime_runs_before_commands(self, mocker) -> None:
        order: list[str] = []
        from sysup.capabilities.sudo import SudoPrime

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
        cmd = _cmd(steps=[["brew", "update"]])

        list(Runner(_cfg(prime=("sudo-prime",))).run([("brew", cmd)]))

        assert order[0] == "primed"
        assert "step" in order

    def test_stop_called_in_finally_on_keyboardinterrupt(self, mocker) -> None:
        stopped: list[bool] = []
        from sysup.capabilities.sudo import SudoPrime

        prime_cap = mocker.MagicMock(spec=SudoPrime)
        prime_cap.prime.return_value = lambda: stopped.append(True)
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"sudo-prime": prime_cap})
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", side_effect=KeyboardInterrupt())
        cmd = _cmd(steps=[["brew", "update"]])

        with pytest.raises(KeyboardInterrupt):
            list(Runner(_cfg(prime=("sudo-prime",))).run([("brew", cmd)]))

        assert stopped == [True]


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

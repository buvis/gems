from __future__ import annotations

import subprocess

import pytest
from buvis.pybase.result import FatalError

from sysup.config import SysupCommand, SysupConfig
from sysup.runner import Runner
from sysup.step_result import StepResult


def _cmd(**kwargs: object) -> SysupCommand:
    return SysupCommand.model_validate(kwargs)


def _cfg() -> SysupConfig:
    return SysupConfig.model_validate({})


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _log_text(runner: Runner) -> str:
    assert runner.log_path is not None
    return runner.log_path.read_text()


class TestObservabilityRepeatsAndContinue:
    def test_repeated_error_lines_are_all_kept_and_counted(self, mocker) -> None:
        from sysup.runner import _scan_errors

        assert _scan_errors("error: x\nerror: x", "error: x") == ["error: x"] * 3
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", return_value=_proc(stdout="error: x\nerror: x", stderr="error: x"))
        failure = mocker.patch("sysup.runner.console.failure")

        steps = list(Runner(_cfg()).run([("brew", _cmd(steps=[["brew", "upgrade"]]))]))

        assert [c.args[0] for c in failure.call_args_list] == ["error: x"] * 3
        assert steps == [StepResult("brew", True, "brew: 3 error line(s), see log", status="warned", command="brew")]

    @pytest.mark.parametrize(
        "outputs,status,printed",
        [
            ([_proc(), _proc(), _proc()], "ok", []),
            ([_proc(stdout="error: x"), _proc(), _proc()], "warned", ["error: x"]),
            (
                [_proc(1, stderr="first boom"), _proc(stdout="error: y"), _proc(stderr="error: z")],
                "failed",
                ["error: y", "error: z"],
            ),
        ],
        ids=["clean", "warned", "failed"],
    )
    def test_continue_on_error_yields_exactly_one_final_result(self, mocker, outputs, status, printed) -> None:
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mock_run = mocker.patch("sysup.runner.subprocess.run", side_effect=outputs)
        failure = mocker.patch("sysup.runner.console.failure")
        cmd = _cmd(continue_on_error=True, steps=[["a"], ["b"], ["c"]])

        steps = list(Runner(_cfg()).run([("multi", cmd)]))

        assert mock_run.call_count == 3
        assert [(s.status, s.success, s.command) for s in steps] == [(status, status != "failed", "multi")]
        # Successful steps after an earlier failure are still scanned.
        assert [c.args[0] for c in failure.call_args_list] == printed


class TestObservabilityStepLog:
    @pytest.mark.parametrize(
        "options,binary,returncode,marker",
        [
            ({"interactive": True}, "/bin/npm-check", 0, "=== tool: npm-check -gu (ok, not captured) ==="),
            ({"interactive": True}, "/bin/npm-check", 3, "=== tool: npm-check -gu (failed, not captured) ==="),
            ({}, None, 0, "=== tool: npm-check -gu (failed, not captured) ==="),
        ],
        ids=["interactive-ok", "interactive-failed", "binary-missing"],
    )
    def test_unspawned_or_interactive_step_logged_not_captured(
        self, mocker, options, binary, returncode: int, marker
    ) -> None:
        mocker.patch("sysup.runner.shutil.which", return_value=binary)
        mocker.patch("sysup.runner.subprocess.run", return_value=_proc(returncode))
        runner = Runner(_cfg())

        list(runner.run([("tool", _cmd(steps=[["npm-check", "-gu"]], **options))]))

        assert runner.log_path is not None
        text = runner.log_path.read_text()
        assert marker in text
        assert "(exit " not in text

    def test_timed_out_step_logged_with_timeout_marker_and_partial_output(self, mocker) -> None:
        exc = subprocess.TimeoutExpired(cmd=["mise"], timeout=30, output=b"partial-out", stderr=b"partial-err")
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", side_effect=exc)
        runner = Runner(_cfg())

        steps = list(runner.run([("mise", _cmd(steps=[["mise", "self-update"]], timeout=30))]))

        text = _log_text(runner)
        assert "=== mise: mise self-update (timed out after 30s) ===\npartial-out\npartial-err" in text
        assert "not captured" not in text
        assert [s.status for s in steps] == ["failed"]

    def test_successful_steps_logged_with_exit_zero_and_output(self, mocker) -> None:
        outputs = [_proc(stdout="fetched 3 formulae"), _proc(stdout="upgraded jq", stderr="note: done")]
        mocker.patch("sysup.runner.shutil.which", side_effect=lambda n: "/bin/" + n)
        mocker.patch("sysup.runner.subprocess.run", side_effect=outputs)
        runner = Runner(_cfg())

        list(runner.run([("brew", _cmd(steps=[["brew", "update"], ["brew", "upgrade"]]))]))

        text = _log_text(runner)
        assert "=== brew: brew update (exit 0) ===\nfetched 3 formulae\n" in text
        assert "=== brew: brew upgrade (exit 0) ===\nupgraded jq\nnote: done" in text


class TestObservabilityUseLog:
    @staticmethod
    def _run_cap(mocker, results) -> tuple[Runner, list[StepResult]]:
        cap = mocker.MagicMock()
        cap.run.return_value = results
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        runner = Runner(_cfg())
        return runner, list(runner.run([("pkgs", _cmd(use="pip-outdated"))]))

    def test_each_capability_step_logged_with_its_status(self, mocker) -> None:
        results = iter(
            [
                StepResult("pip (3.12)", True),
                StepResult("pip (3.13)", False, "numpy failed"),
                StepResult("pip (3.14)", True, "soon", status="expiring"),
                StepResult("pip (3.15)", True, "odd", status="warned"),
            ]
        )
        runner, steps = self._run_cap(mocker, results)

        text = _log_text(runner)
        assert len(steps) == 4
        for status in ("ok", "failed", "expiring", "warned"):
            assert text.count(f"=== pkgs: pip-outdated ({status}, not captured) ===") == 1

    def test_capability_raising_mid_iteration_logs_yielded_then_synthetic_failure(self, mocker) -> None:
        def generate():
            yield StepResult("pip (3.12)", True)
            raise RuntimeError("iterator failed")

        runner, steps = self._run_cap(mocker, generate())

        assert runner.log_path is not None
        text = runner.log_path.read_text()
        ok_at = text.index("=== pkgs: pip-outdated (ok, not captured) ===")
        failed_at = text.index("=== pkgs: pip-outdated (failed, not captured) ===")
        assert ok_at < failed_at
        assert steps[-1] == StepResult("pkgs", False, "pkgs failed: iterator failed", command="pkgs")

    def test_fatal_error_propagates_without_logging_a_failure(self, mocker) -> None:
        def generate():
            yield StepResult("pip (3.12)", True)
            raise FatalError("fatal iterator")

        cap = mocker.MagicMock()
        cap.run.return_value = generate()
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        runner = Runner(_cfg())

        with pytest.raises(FatalError, match="fatal iterator"):
            list(runner.run([("pkgs", _cmd(use="pip-outdated"))]))

        assert runner.log_path is not None
        text = runner.log_path.read_text()
        assert "=== pkgs: pip-outdated (ok, not captured) ===" in text
        assert "(failed, not captured)" not in text

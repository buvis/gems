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


def _proc(returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr="")


class TestObservabilityStepLog:
    @pytest.mark.parametrize(
        "options,binary,marker",
        [
            ({"interactive": True}, "/bin/npm-check", "=== tool: npm-check -gu (ok, not captured) ==="),
            ({}, None, "=== tool: npm-check -gu (failed, not captured) ==="),
        ],
        ids=["interactive", "binary-missing"],
    )
    def test_unspawned_or_interactive_step_logged_not_captured(self, mocker, options, binary, marker) -> None:
        mocker.patch("sysup.runner.shutil.which", return_value=binary)
        mocker.patch("sysup.runner.subprocess.run", return_value=_proc())
        runner = Runner(_cfg())

        list(runner.run([("tool", _cmd(steps=[["npm-check", "-gu"]], **options))]))

        assert runner.log_path is not None
        text = runner.log_path.read_text()
        assert marker in text
        assert "(exit " not in text


class TestObservabilityUseLog:
    @staticmethod
    def _run_cap(mocker, results) -> tuple[Runner, list[StepResult]]:
        cap = mocker.MagicMock()
        cap.run.return_value = results
        mocker.patch.dict("sysup.runner.CAPABILITIES", {"pip-outdated": cap})
        runner = Runner(_cfg())
        return runner, list(runner.run([("pkgs", _cmd(use="pip-outdated"))]))

    def test_each_capability_step_logged_with_its_status(self, mocker) -> None:
        results = iter([StepResult("pip (3.12)", True), StepResult("pip (3.13)", False, "numpy failed")])
        runner, steps = self._run_cap(mocker, results)

        assert runner.log_path is not None
        text = runner.log_path.read_text()
        assert len(steps) == 2
        assert text.count("=== pkgs: pip-outdated (ok, not captured) ===") == 1
        assert text.count("=== pkgs: pip-outdated (failed, not captured) ===") == 1

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

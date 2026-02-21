from __future__ import annotations

import shutil
import subprocess

from buvis.pybase.result import FatalError

from sysup.commands.step_result import StepResult


class CommandWsl:
    def execute(self: CommandWsl) -> list[StepResult]:
        apt_path = shutil.which("apt")
        if apt_path is None:
            raise FatalError("apt not found")

        steps: list[StepResult] = []
        steps.append(self._run(["sudo", apt_path, "update"], "apt update"))
        steps.append(self._run(["sudo", apt_path, "upgrade", "-y"], "apt upgrade"))
        steps.append(self._run(["sudo", apt_path, "autoremove", "-y"], "apt autoremove"))

        snap_path = shutil.which("snap")
        if snap_path is None:
            steps.append(StepResult("snap", success=False, message="snap not found, skipping"))
            return steps

        steps.append(self._run(["sudo", snap_path, "refresh"], "snap"))
        return steps

    def _run(self: CommandWsl, command: list[str], label: str) -> StepResult:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return StepResult(label, success=True)

        message = result.stderr.strip() or "unknown error"
        return StepResult(label, success=False, message=f"{label} failed: {message}")

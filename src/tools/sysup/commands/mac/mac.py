from __future__ import annotations

import shutil
import subprocess

from buvis.pybase.result import FatalError

from sysup.commands.step_result import StepResult


class CommandMac:
    def execute(self: CommandMac) -> list[StepResult]:
        brew_path = shutil.which("brew")
        if brew_path is None:
            raise FatalError("brew not found")

        steps: list[StepResult] = []

        brew_ok = True
        for args in ([brew_path, "update"], [brew_path, "upgrade"], [brew_path, "cleanup"]):
            result = subprocess.run(args, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                message = result.stderr.strip() or "unknown error"
                steps.append(StepResult("brew", success=False, message=f"brew update failed: {message}"))
                brew_ok = False
                break
        if brew_ok:
            steps.append(StepResult("brew", success=True))

        steps.extend(self._run_optional("mise", ["mise", "upgrade"], "mise"))
        steps.extend(self._run_optional_interactive("npm-check", ["npm-check", "-gu"], "npm-check"))

        from sysup.commands.pip.pip import CommandPip

        steps.extend(CommandPip().execute())

        steps.extend(self._run_optional("uv", ["uv", "tool", "upgrade", "--all"], "uv tools"))
        steps.extend(self._run_optional("helm", ["helm", "repo", "update"], "helm repos"))

        return steps

    def _run_optional(self: CommandMac, binary: str, command: list[str], label: str) -> list[StepResult]:
        binary_path = shutil.which(binary)
        if binary_path is None:
            return [StepResult(label, success=False, message=f"{binary} not found, skipping")]

        resolved = [binary_path, *command[1:]]
        result = subprocess.run(resolved, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return [StepResult(label, success=True)]

        message = result.stderr.strip() or "unknown error"
        return [StepResult(label, success=False, message=f"{label} update failed: {message}")]

    def _run_optional_interactive(self: CommandMac, binary: str, command: list[str], label: str) -> list[StepResult]:
        binary_path = shutil.which(binary)
        if binary_path is None:
            return [StepResult(label, success=False, message=f"{binary} not found, skipping")]

        resolved = [binary_path, *command[1:]]
        result = subprocess.run(resolved, check=False)
        if result.returncode == 0:
            return [StepResult(label, success=True)]

        return [StepResult(label, success=False, message=f"{label} update failed: exit code {result.returncode}")]

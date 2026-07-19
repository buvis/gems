from __future__ import annotations

import shutil
import subprocess
import threading
from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from sysup.commands.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Callable


class CommandMac:
    def execute(self: CommandMac) -> list[StepResult]:
        brew_path = shutil.which("brew")
        if brew_path is None:
            raise FatalError("brew not found")

        stop_sudo_refresh = self._prime_sudo()
        try:
            return self._run_steps(brew_path)
        finally:
            stop_sudo_refresh()

    def _run_steps(self: CommandMac, brew_path: str) -> list[StepResult]:
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

        steps.extend(self._run_optional_interactive("npm-check", ["npm-check", "-gu"], "npm-check"))

        from sysup.commands.pip.pip import CommandPip

        steps.extend(CommandPip().execute())

        steps.extend(self._run_optional("uv", ["uv", "tool", "upgrade", "--all"], "uv tools"))
        steps.extend(self._run_optional("helm", ["helm", "repo", "update"], "helm repos"))

        # mise upgrade deletes replaced tool version dirs that the inherited PATH
        # still points at, so it must run after every other tool lookup.
        steps.extend(self._run_optional("mise", ["mise", "upgrade"], "mise"))

        return steps

    def _prime_sudo(self: CommandMac) -> Callable[[], None]:
        """Cache sudo credentials upfront so brew casks don't prompt mid-run.

        Returns a stop callback for the background refresher that keeps the
        ticket fresh past sudo's 5-minute timeout. A missing sudo or a declined
        prompt is not an error: later steps then prompt as before.
        """
        sudo_path = shutil.which("sudo")
        if sudo_path is None:
            return lambda: None
        prime = subprocess.run([sudo_path, "-v"], check=False)
        if prime.returncode != 0:
            return lambda: None

        stop = threading.Event()

        def refresh() -> None:
            while not stop.wait(60):
                subprocess.run([sudo_path, "-n", "-v"], capture_output=True, check=False)

        threading.Thread(target=refresh, daemon=True).start()
        return stop.set

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

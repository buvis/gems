from __future__ import annotations

import json
import subprocess
import sys

from sysup.commands.step_result import StepResult


class CommandPip:
    def execute(self: CommandPip) -> list[StepResult]:
        steps: list[StepResult] = []

        update_pip = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
            check=False,
        )
        if update_pip.returncode == 0:
            steps.append(StepResult("pip", success=True))
        else:
            message = update_pip.stderr.strip() or "unknown error"
            steps.append(StepResult("pip", success=False, message=f"pip update failed: {message}"))

        outdated_result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if outdated_result.returncode != 0:
            message = outdated_result.stderr.strip() or "unknown error"
            steps.append(StepResult("pip outdated", success=False, message=f"outdated package check failed: {message}"))
            return steps

        try:
            outdated_packages = json.loads(outdated_result.stdout)
        except json.JSONDecodeError as exc:
            steps.append(StepResult("pip outdated", success=False, message=f"failed to parse outdated packages: {exc}"))
            return steps

        if not outdated_packages:
            steps.append(StepResult("pip packages", success=True, message="no outdated packages"))
            return steps

        for package in outdated_packages:
            package_name = package.get("name")
            if not isinstance(package_name, str) or not package_name:
                continue

            package_update = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if package_update.returncode == 0:
                steps.append(StepResult(package_name, success=True))
            else:
                message = package_update.stderr.strip() or "unknown error"
                steps.append(
                    StepResult(package_name, success=False, message=f"{package_name} update failed: {message}")
                )

        return steps

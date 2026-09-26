from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

__all__ = ["PipOutdated"]


def _find_interpreters() -> list[tuple[str, str]]:
    """Return (name, path) of mise-managed pythons, or the PATH python3 as fallback.

    sysup's own interpreter is a uv-built venv without pip, so sys.executable
    is never a valid target.
    """
    mise = shutil.which("mise")
    if mise is not None:
        result = subprocess.run(
            [mise, "ls", "--json", "python"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            try:
                installs = json.loads(result.stdout)
            except json.JSONDecodeError:
                installs = []
            interpreters = []
            for install in installs if isinstance(installs, list) else []:
                if not isinstance(install, dict):
                    continue
                install_path = install.get("install_path")
                if not isinstance(install_path, str) or not install_path:
                    continue
                python = Path(install_path) / "bin" / "python3"
                if python.is_file():
                    version = install.get("version")
                    name = version if isinstance(version, str) and version else Path(install_path).name
                    interpreters.append((name, str(python)))
            if interpreters:
                return interpreters
    python3 = shutil.which("python3")
    return [("python3", python3)] if python3 else []


class PipOutdated:
    """Per-interpreter outdated-package discovery and upgrade.

    Targets every mise-managed python (falling back to PATH's python3), upgrades
    pip, then upgrades each outdated package individually.
    """

    @property
    def inputs(self: PipOutdated) -> Mapping[str, object]:
        return {}

    def run(self: PipOutdated, **kwargs: object) -> Iterator[StepResult]:  # noqa: ARG002
        interpreters = _find_interpreters()
        if not interpreters:
            yield StepResult("pip", success=False, message="no python interpreter found, skipping")
            return

        for name, python in interpreters:
            yield from self._update_interpreter(name, python)

    def _update_interpreter(self: PipOutdated, name: str, python: str) -> list[StepResult]:
        steps: list[StepResult] = []

        probe = subprocess.run(
            [python, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            return [
                StepResult(
                    f"pip ({name})",
                    success=False,
                    message=f"pip not available in python {name}, skipping",
                ),
            ]

        update_pip = subprocess.run(
            [python, "-m", "pip", "install", "--upgrade", "pip"],
            capture_output=True,
            text=True,
            check=False,
        )
        if update_pip.returncode == 0:
            steps.append(StepResult(f"pip ({name})", success=True))
        else:
            message = update_pip.stderr.strip() or "unknown error"
            steps.append(StepResult(f"pip ({name})", success=False, message=f"pip update failed: {message}"))

        outdated_result = subprocess.run(
            [python, "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if outdated_result.returncode != 0:
            message = outdated_result.stderr.strip() or "unknown error"
            steps.append(
                StepResult(
                    f"pip outdated ({name})",
                    success=False,
                    message=f"outdated package check failed: {message}",
                ),
            )
            return steps

        try:
            outdated_packages = json.loads(outdated_result.stdout)
        except json.JSONDecodeError as exc:
            steps.append(
                StepResult(
                    f"pip outdated ({name})",
                    success=False,
                    message=f"failed to parse outdated packages: {exc}",
                ),
            )
            return steps

        if not outdated_packages:
            steps.append(StepResult(f"pip packages ({name})", success=True, message="no outdated packages"))
            return steps

        steps.extend(self._update_packages(name, python, outdated_packages))
        return steps

    def _update_packages(
        self: PipOutdated,
        name: str,
        python: str,
        outdated_packages: list[dict[str, object]],
    ) -> list[StepResult]:
        steps: list[StepResult] = []
        for package in outdated_packages:
            package_name = package.get("name")
            if not isinstance(package_name, str) or not package_name:
                continue

            package_update = subprocess.run(
                [python, "-m", "pip", "install", "--upgrade", package_name],
                capture_output=True,
                text=True,
                check=False,
            )
            label = f"{package_name} ({name})"
            if package_update.returncode == 0:
                steps.append(StepResult(label, success=True))
            else:
                message = package_update.stderr.strip() or "unknown error"
                steps.append(StepResult(label, success=False, message=f"{package_name} update failed: {message}"))

        return steps

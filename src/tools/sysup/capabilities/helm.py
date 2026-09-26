from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

__all__ = ["HelmRepoUpdate"]


class HelmRepoUpdate:
    """`helm repo update` guarded against an empty repo list.

    `helm repo update` errors when no repos are configured; treat that as a
    no-op. A failing or unparseable repo list falls through to the update so
    real problems still surface as a failed step.
    """

    @property
    def inputs(self: HelmRepoUpdate) -> Mapping[str, object]:
        return {}

    def run(self: HelmRepoUpdate, **kwargs: object) -> Iterator[StepResult]:  # noqa: ARG002
        helm_path = shutil.which("helm")
        if helm_path is None:
            yield StepResult("helm repos", success=False, message="helm not found, skipping")
            return

        listing = subprocess.run(
            [helm_path, "repo", "list", "-o", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
        if listing.returncode == 0:
            try:
                repos = json.loads(listing.stdout)
            except json.JSONDecodeError:
                repos = None
            if repos == []:
                yield StepResult("helm repos", success=True, message="no helm repos configured, skipping")
                return

        yield self._run_update(helm_path)

    def _run_update(self: HelmRepoUpdate, helm_path: str) -> StepResult:
        result = subprocess.run(
            [helm_path, "repo", "update"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return StepResult("helm repos", success=True)

        message = result.stderr.strip() or "unknown error"
        return StepResult("helm repos", success=False, message=f"helm repos update failed: {message}")

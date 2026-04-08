from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterator

from buvis.pybase.result import FatalError

from sysup.commands.step_result import StepResult


class CommandNvim:
    MASON_TIMEOUT: int = 300

    def execute(
        self: CommandNvim,
        on_step_start: Callable[[str], None] | None = None,
    ) -> Iterator[StepResult]:
        nvim_path = shutil.which("nvim")
        if nvim_path is None:
            raise FatalError("nvim not found")

        if on_step_start:
            on_step_start("lazy")
        yield self._sync_lazy(nvim_path)

        if on_step_start:
            on_step_start("mason")
        yield self._update_mason(nvim_path)

        if on_step_start:
            on_step_start("treesitter")
        yield self._update_treesitter(nvim_path)

    def _sync_lazy(self: CommandNvim, nvim_path: str) -> StepResult:
        result = subprocess.run(
            [nvim_path, "--headless", "+Lazy! sync", "+qa"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return StepResult("lazy", success=True)
        message = result.stderr.strip() or "unknown error"
        return StepResult("lazy", success=False, message=f"lazy sync failed: {message}")

    def _update_mason(self: CommandNvim, nvim_path: str) -> StepResult:
        try:
            result = subprocess.run(
                [
                    nvim_path,
                    "--headless",
                    "-c",
                    "autocmd User MasonToolsUpdateCompleted quitall",
                    "-c",
                    "MasonToolsUpdate",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.MASON_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            detail = ""
            raw = exc.stderr or exc.stdout or b""
            captured = raw.decode(errors="replace").strip() if isinstance(raw, bytes) else raw.strip()
            if captured:
                detail = f"\n{captured}"
            return StepResult(
                "mason",
                success=False,
                message=f"mason update timed out after {self.MASON_TIMEOUT}s{detail}",
            )
        if result.returncode == 0:
            return StepResult("mason", success=True)
        message = result.stderr.strip() or "unknown error"
        return StepResult("mason", success=False, message=f"mason update failed: {message}")

    def _update_treesitter(self: CommandNvim, nvim_path: str) -> StepResult:
        result = subprocess.run(
            [nvim_path, "--headless", "+TSUpdateSync", "+qa"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return StepResult("treesitter", success=True)
        message = result.stderr.strip() or "unknown error"
        return StepResult("treesitter", success=False, message=f"treesitter update failed: {message}")

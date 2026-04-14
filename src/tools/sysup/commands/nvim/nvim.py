from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

from buvis.pybase.result import FatalError

from sysup.commands.step_result import StepResult

_MASON_LOG_TAIL_LINES = 200
_MASON_LOG_TAIL_BYTES = 8192

_MASON_PROBE_LUA = (
    "lua "
    "local ok_reg, r = pcall(require, 'mason-registry') "
    "if not ok_reg then print('mason INCONCLUSIVE mason-registry unavailable') return end "
    "local ok_ti, ti = pcall(require, 'mason-tool-installer') "
    "if not ok_ti or type(ti) ~= 'table' or type(ti.config) ~= 'table' "
    "or type(ti.config.ensure_installed) ~= 'table' then "
    "print('mason INCONCLUSIVE mason-tool-installer config unavailable') return end "
    "for _, name in ipairs(r.get_installed_package_names()) do print('mason OK ' .. name) end "
    "for _, entry in ipairs(ti.config.ensure_installed) do "
    "local name = type(entry) == 'table' and entry[1] or entry "
    "if type(name) == 'string' and not r.is_installed(name) then "
    "print('mason FAIL ' .. name) end end"
)


class CommandNvim:
    MASON_TIMEOUT: int = 600

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
                    "Lazy load mason.nvim mason-tool-installer.nvim",
                    "-c",
                    "MasonToolsUpdateSync",
                    "-c",
                    _MASON_PROBE_LUA,
                    "+qa",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.MASON_TIMEOUT,
            )
        except subprocess.TimeoutExpired as exc:
            parts = [f"mason update timed out after {self.MASON_TIMEOUT}s"]
            raw = exc.stderr or exc.stdout or b""
            captured = raw.decode(errors="replace").strip() if isinstance(raw, bytes) else raw.strip()
            if captured:
                parts.append(captured)
            tail = self._read_mason_log_tail()
            if tail:
                parts.append(f"mason.log tail:\n{tail}")
            return StepResult("mason", success=False, message="\n".join(parts))

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        failed = [line[len("mason FAIL ") :].strip() for line in stdout.splitlines() if line.startswith("mason FAIL ")]
        inconclusive = [line for line in stdout.splitlines() if line.startswith("mason INCONCLUSIVE")]

        if result.returncode != 0:
            message = "\n".join(p for p in (stderr.strip(), stdout.strip()) if p) or "unknown error"
            return StepResult("mason", success=False, message=f"mason update failed: {message}")

        if failed:
            parts = [f"mason tools failed to install: {', '.join(failed)}"]
            tail = self._read_mason_log_tail()
            if tail:
                parts.append(f"mason.log tail:\n{tail}")
            return StepResult("mason", success=False, message="\n".join(parts))

        if inconclusive:
            return StepResult("mason", success=True, message=inconclusive[0])

        return StepResult("mason", success=True)

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

    def _read_mason_log_tail(self: CommandNvim) -> str:
        candidates: list[Path] = []
        xdg_state = os.environ.get("XDG_STATE_HOME")
        if xdg_state:
            candidates.append(Path(xdg_state) / "nvim" / "mason.log")
        home = os.environ.get("HOME")
        if home:
            candidates.append(Path(home) / ".local" / "state" / "nvim" / "mason.log")

        for path in candidates:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            tail = "".join(lines[-_MASON_LOG_TAIL_LINES:])
            encoded = tail.encode()
            if len(encoded) > _MASON_LOG_TAIL_BYTES:
                tail = encoded[-_MASON_LOG_TAIL_BYTES:].decode(errors="replace")
            return tail
        return ""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import deque
from collections.abc import Callable, Iterator
from pathlib import Path

from buvis.pybase.result import FatalError

from sysup.commands.step_result import StepResult

_MASON_LOG_TAIL_LINES = 200
_MASON_LOG_TAIL_BYTES = 8192

# Strips ANSI OSC sequences (ESC ] ... BEL or ESC ] ... ESC \) and CSI
# sequences (ESC [ ... <letter>). Required because iTerm2 shell integration
# injects OSC 1337 user-var escapes around print() output without intervening
# newlines, which otherwise glues itself to the probe's `mason DONE` /
# `mason FAIL <name>` markers and breaks substring matching.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]")

# Registers a mason-registry listener for package:install:failed before
# MasonToolsUpdateSync runs. The registry emits the mason package name the
# installer tried to install (already resolved through mason-lspconfig /
# mason-nvim-dap / mason-null-ls integrations by mason-tool-installer), so we
# avoid the lspconfig-name-vs-mason-package-name mismatch that arose when
# probing ensure_installed entries directly via mason-registry.is_installed.
_MASON_REGISTER_LISTENER_LUA = (
    "lua "
    "local ok, err = pcall(function() "
    "local ok_reg, mr = pcall(require, 'mason-registry') "
    "if not ok_reg then print('mason INCONCLUSIVE mason-registry unavailable') return end "
    "_G._sysup_mason_failed = {} "
    "mr:on('package:install:failed', function(pkg) "
    "table.insert(_G._sysup_mason_failed, pkg.name) end) end) "
    "if not ok then print('mason INCONCLUSIVE listener setup error: ' .. tostring(err)) end"
)

# Drains the captured failures and prints a `mason DONE` sentinel so the
# Python side can tell `probe ran with no failures` from `nvim never reached
# the report step`.
_MASON_REPORT_LUA = (
    "lua for _, name in ipairs(_G._sysup_mason_failed or {}) do print('mason FAIL ' .. name) end print('mason DONE')"
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
                    _MASON_REGISTER_LISTENER_LUA,
                    "-c",
                    "MasonToolsUpdateSync",
                    "-c",
                    _MASON_REPORT_LUA,
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
        combined = (stdout + ("\n" if stdout and stderr else "") + stderr).strip()
        combined = _ANSI_ESCAPE_RE.sub("", combined)
        lines = combined.splitlines()
        failed = [line[len("mason FAIL ") :].strip() for line in lines if line.startswith("mason FAIL ")]
        inconclusive = [line for line in lines if line.startswith("mason INCONCLUSIVE")]
        probe_done = any(line.strip() == "mason DONE" for line in lines)

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

        if not probe_done:
            return StepResult(
                "mason",
                success=True,
                message="mason INCONCLUSIVE probe produced no output",
            )

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
                    last_lines = deque(fh, maxlen=_MASON_LOG_TAIL_LINES)
            except OSError:
                continue
            tail = "".join(last_lines)
            encoded = tail.encode()
            if len(encoded) > _MASON_LOG_TAIL_BYTES:
                tail = encoded[-_MASON_LOG_TAIL_BYTES:].decode(errors="replace")
            return tail
        return ""

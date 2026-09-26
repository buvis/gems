from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

__all__ = ["NvimMason"]

_MASON_DEFAULT_TIMEOUT = 600
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


class NvimMason:
    """Drive Mason tool updates via a headless nvim Lua probe.

    Registers a ``package:install:failed`` listener, runs
    ``MasonToolsUpdateSync``, prints sentinels, strips ANSI, parses
    ``mason FAIL <name>`` / ``mason DONE``, honours a ``timeout`` (default 600s),
    and tails ``mason.log`` on failure.
    """

    @property
    def inputs(self: NvimMason) -> Mapping[str, object]:
        return {"timeout": _MASON_DEFAULT_TIMEOUT}

    def run(self: NvimMason, **kwargs: object) -> Iterator[StepResult]:
        timeout_input = kwargs.get("timeout", _MASON_DEFAULT_TIMEOUT)
        timeout = int(timeout_input) if isinstance(timeout_input, (int, str)) else _MASON_DEFAULT_TIMEOUT
        nvim_path = self._resolve_nvim()
        yield self._update_mason(nvim_path, timeout)

    def _resolve_nvim(self: NvimMason) -> str:
        # Re-resolved before the step: a concurrent `mise upgrade` deletes the
        # version-pinned install dir a single startup resolution points at.
        nvim_path = shutil.which("nvim")
        if nvim_path is None:
            msg = "nvim not found"
            raise FatalError(msg)
        return nvim_path

    def _update_mason(self: NvimMason, nvim_path: str, timeout: int) -> StepResult:
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
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            parts = [f"mason update timed out after {timeout}s"]
            raw = exc.stderr or exc.stdout or b""
            captured = raw.decode(errors="replace").strip() if isinstance(raw, bytes) else raw.strip()
            captured = _ANSI_ESCAPE_RE.sub("", captured).strip()
            if captured:
                parts.append(captured)
            tail = self._read_mason_log_tail()
            if tail:
                parts.append(f"mason.log tail:\n{tail}")
            return StepResult("mason", success=False, message="\n".join(parts))
        except OSError as exc:
            return StepResult("mason", success=False, message=f"mason update failed: {exc}")
        return self._parse_mason_result(result)

    def _parse_mason_result(self: NvimMason, result: subprocess.CompletedProcess[str]) -> StepResult:
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

    def _read_mason_log_tail(self: NvimMason) -> str:
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

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.filesystem.atomic_write import atomic_write_text

from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

__all__ = ["PipxPython"]

_DEFAULT_CONFIG = "~/.config/mise/config.toml"
_PIN = re.compile(r'^"(pipx:[^"]+)" = .*--managed-python --python (\d+\.\d+)', re.MULTILINE)
_MINOR = re.compile(r"^(\d+\.\d+)")


def _set_pin(path: Path, tool: str, version: str) -> None:
    pattern = re.compile(rf'^("{re.escape(tool)}" = .*--managed-python --python )\d+\.\d+', re.MULTILINE)
    atomic_write_text(path, pattern.sub(rf"\g<1>{version}", path.read_text(), count=1))


class PipxPython:
    """Move mise pipx tools pinned to uv-managed python onto the global mise python minor.

    Only entries whose ``uvx_args`` carry ``--managed-python --python X.Y`` are
    touched, in the mise config and in its ``config.local.toml`` sibling. Each
    stale pin is rewritten in the file it came from and the tool is reinstalled;
    a tool that fails to install on the new minor is reverted to its old pin and
    reinstalled there, so one bad wheel never leaves it broken.
    """

    @property
    def inputs(self: PipxPython) -> Mapping[str, object]:
        return {"config": _DEFAULT_CONFIG}

    def run(self: PipxPython, **kwargs: object) -> Iterator[StepResult]:
        mise, uv = shutil.which("mise"), shutil.which("uv")
        if mise is None or uv is None:
            yield StepResult("pipx python", success=False, message="mise or uv not found, skipping")
            return

        path = Path(str(kwargs.get("config", _DEFAULT_CONFIG))).expanduser()
        if not path.is_file():
            yield StepResult("pipx python", success=False, message=f"{path} not found, skipping")
            return

        target = self._global_minor(mise)
        if target is None:
            yield StepResult("pipx python", success=False, message="no global mise python version, skipping")
            return

        # mise reads config.local.toml beside config.toml, so pins can live in either.
        local = path.with_name(f"{path.stem}.local{path.suffix}")
        files = [p for p in (path, local) if p.is_file()]
        stale = [
            (p, m.group(1), m.group(2)) for p in files for m in _PIN.finditer(p.read_text()) if m.group(2) != target
        ]
        if not stale:
            yield StepResult("pipx python", success=True, message=f"all pinned pipx tools on python {target}")
            return

        install = subprocess.run([uv, "python", "install", target], capture_output=True, text=True, check=False)
        if install.returncode != 0:
            message = install.stderr.strip() or "unknown error"
            yield StepResult("pipx python", success=False, message=f"uv python install {target} failed: {message}")
            return

        for file, tool, old in stale:
            yield self._move(mise, file, tool, old, target)

    def _global_minor(self: PipxPython, mise: str) -> str | None:
        # Run from $HOME so a project-local python pin can't redefine the target.
        result = subprocess.run(
            [mise, "current", "python"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path.home(),
        )
        match = _MINOR.match(result.stdout.strip()) if result.returncode == 0 else None
        return match.group(1) if match else None

    def _move(self: PipxPython, mise: str, path: Path, tool: str, old: str, target: str) -> StepResult:
        label = f"{tool} (python {old} -> {target})"
        _set_pin(path, tool, target)
        result = subprocess.run([mise, "install", "-f", tool], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return StepResult(label, success=True)

        message = result.stderr.strip() or "unknown error"
        _set_pin(path, tool, old)
        restore = subprocess.run([mise, "install", "-f", tool], capture_output=True, text=True, check=False)
        state = f"kept on python {old}" if restore.returncode == 0 else f"reinstall on python {old} also failed"
        return StepResult(label, success=False, message=f"{state}: {message}")

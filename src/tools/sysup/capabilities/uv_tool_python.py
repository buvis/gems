from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import tomllib

from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

__all__ = ["UvToolPython"]

_MINOR = re.compile(r"^(\d+\.\d+)")
_VERSION = re.compile(r"(\d+\.\d+)(?:\.\d+)?(?:(?:a|b|rc)\d+)?")


def _tool_dir(uv: str) -> Path:
    result = subprocess.run([uv, "tool", "dir"], capture_output=True, text=True, check=False)
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    data_home = os.environ.get("XDG_DATA_HOME")
    return Path(data_home) / "uv/tools" if data_home else Path.home() / ".local/share/uv/tools"


def _global_minor(mise: str) -> str | None:
    # Ignore project-local Python pins when choosing the target.
    result = subprocess.run([mise, "current", "python"], capture_output=True, text=True, check=False, cwd=Path.home())
    match = _MINOR.match(result.stdout.strip()) if result.returncode == 0 else None
    return match.group(1) if match else None


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.lower())


def _pinned_minor(receipt_path: Path) -> str | None:
    with receipt_path.open("rb") as receipt:
        data = tomllib.load(receipt)
    tool = data.get("tool")
    if not isinstance(tool, dict):
        raise ValueError("missing tool table")
    allowed = {
        "requirements",
        "python",
        "constraints",
        "overrides",
        "excludes",
        "build-constraint-dependencies",
        "options",
        "entrypoints",
    }
    if tool.keys() - allowed or tool.get("options", {}) != {}:
        raise ValueError("unsupported receipt customization")
    requirements = tool.get("requirements")
    if not isinstance(requirements, list) or len(requirements) != 1:
        raise ValueError("unsupported requirements identity")
    requirement = requirements[0]
    if isinstance(requirement, dict):
        if (
            requirement.keys() - {"name", "extras", "specifier"}
            or requirement.get("extras", []) != []
            or requirement.get("specifier", "") != ""
        ):
            raise ValueError("unsupported requirement customization")
        requirement = requirement.get("name")
    name = _normalize(receipt_path.parent.name)
    if not isinstance(requirement, str) or _normalize(requirement) != name:
        raise ValueError("unsupported requirements identity")
    dependency_keys = ("constraints", "overrides", "excludes", "build-constraint-dependencies")
    if any(tool.get(key, []) != [] for key in dependency_keys):
        raise ValueError("unsupported dependency customization")
    entrypoints = tool.get("entrypoints", [])
    if not isinstance(entrypoints, list):
        raise ValueError("unsupported entrypoints")
    for entrypoint in entrypoints:
        source = entrypoint.get("from", "") if isinstance(entrypoint, dict) else None
        if not isinstance(source, str) or (source and _normalize(source) != name):
            raise ValueError("unsupported entrypoint source")
    if "python" not in tool:
        return None
    selector = tool["python"]
    match = _VERSION.fullmatch(selector) if isinstance(selector, str) else None
    if match is None:
        raise ValueError(f"unsupported python selector: {selector!r}")
    return match.group(1)


def _install_error(argv: list[str]) -> str | None:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        return str(exc)
    return None if result.returncode == 0 else result.stderr.strip() or "unknown error"


class UvToolPython:
    """Move plain uv tool installations to the global mise Python minor."""

    @property
    def inputs(self: UvToolPython) -> Mapping[str, object]:
        return {}

    def run(self: UvToolPython, **_kwargs: object) -> Iterator[StepResult]:
        uv, mise = shutil.which("uv"), shutil.which("mise")
        label = "uv tool python"
        if uv is None or mise is None:
            yield StepResult(label, success=False, message="uv or mise not found, skipping")
            return
        try:
            target = _global_minor(mise)
            if target is None:
                yield StepResult(label, success=False, message="no global mise python version, skipping")
                return
            root = _tool_dir(uv)
            try:
                tools = sorted(path for path in root.iterdir() if not path.name.startswith(".") and path.is_dir())
            except FileNotFoundError:
                tools = []
        except OSError as exc:
            yield StepResult(label, success=False, message=str(exc))
            return
        if not tools:
            yield StepResult(label, success=True, message="no uv tools installed")
            return

        moves: list[tuple[str, str | None]] = []
        skipped = newer = False
        target_version = tuple(map(int, target.split(".")))
        for directory in tools:
            try:
                old = _pinned_minor(directory / "uv-receipt.toml")
            except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
                skipped = True
                yield StepResult(directory.name, success=False, message=f"{exc}, skipping")
                continue
            version = tuple(map(int, old.split("."))) if old is not None else None
            if version is None or version < target_version:
                moves.append((directory.name, old))
            newer |= version is not None and version > target_version
        if not moves:
            if not skipped:
                message = (
                    f"all uv tools pinned to python {target} or newer" if newer else f"all uv tools on python {target}"
                )
                yield StepResult(label, success=True, message=message)
            return
        error = _install_error([uv, "python", "install", target])
        if error is not None:
            yield StepResult(label, success=False, message=f"uv python install {target} failed: {error}")
            return
        for tool, old in moves:
            yield self._move(uv, tool, old, target)

    def _move(self: UvToolPython, uv: str, tool: str, old: str | None, target: str) -> StepResult:
        label = f"{tool} (python {old or 'unpinned'} -> {target})"
        error = _install_error([uv, "tool", "install", "--python", target, "--force", tool])
        if error is None:
            return StepResult(label, success=True)
        rollback = [uv, "tool", "install"]
        if old is not None:
            rollback.extend(["--python", old])
        recovery = _install_error([*rollback, "--force", tool])
        if recovery is None:
            state = f"kept on python {old}" if old else "kept unpinned"
        else:
            state = f"reinstall on python {old} also failed" if old else "unpinned reinstall also failed"
            state = f"{state}: {recovery}"
        return StepResult(label, success=False, message=f"{state}: {error}")

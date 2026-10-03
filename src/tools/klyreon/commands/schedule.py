"""``klyreon schedule install|status|uninstall`` -- manage the external trigger.

Thin command wrappers over :mod:`klyreon.schedule.installer`. The install
resolves the absolute ``klyreon`` binary path and captures the current ``PATH``;
status folds in ``last_maintain`` from state so one line answers "when did
maintenance last run"; uninstall removes the artifact and the manifest entry.
"""

from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

from buvis.pybase.result import CommandResult

from klyreon.schedule import installer
from klyreon.schedule.installer import ScheduleInfo, UnsupportedPlatformError
from klyreon.vault.state import read_state

__all__ = ["CommandScheduleInstall", "CommandScheduleStatus", "CommandScheduleUninstall", "resolve_binary"]

_HHMM_PARTS = 2


def resolve_binary() -> str:
    """Return the absolute path to the ``klyreon`` executable.

    Prefers ``klyreon`` on PATH (the installed console script); falls back to
    ``sys.executable -m klyreon`` form is NOT used — the scheduler needs a
    single argv[0], so we resolve the script path and fall back to the first
    argv entry when it is absolute.
    """
    found = shutil.which("klyreon")
    if found:
        return str(Path(found).resolve())
    argv0 = Path(sys.argv[0])
    if argv0.is_absolute() and argv0.exists():
        return str(argv0.resolve())
    return "klyreon"


def _parse_hhmm(at: str) -> tuple[int, int]:
    parts = at.split(":")
    if len(parts) != _HHMM_PARTS:
        msg = f"--at must be HH:MM, got {at!r}"
        raise ValueError(msg)
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        msg = f"--at out of range (00:00-23:59): {at!r}"
        raise ValueError(msg)
    return hour, minute


class CommandScheduleInstall:
    """Install (or re-install) the platform scheduler artifact."""

    def __init__(
        self,
        *,
        at: str = "03:00",
        binary: str | None = None,
        path_env: str | None = None,
        now: dt.datetime | None = None,
    ) -> None:
        self.at = at
        self.binary = binary
        self.path_env = path_env
        self.now = now

    def execute(self) -> CommandResult:
        try:
            hour, minute = _parse_hhmm(self.at)
        except ValueError as exc:
            return CommandResult(success=False, error=str(exc))

        binary = self.binary or resolve_binary()
        try:
            res = installer.install(
                binary=binary,
                hour=hour,
                minute=minute,
                path_env=self.path_env,
                now=self.now,
            )
        except UnsupportedPlatformError as exc:
            return CommandResult(success=False, error=str(exc))

        return CommandResult(
            success=res.success,
            output=res.message if res.success else None,
            error=res.message if not res.success else None,
            metadata={"artifact": res.artifact_path},
        )


class CommandScheduleStatus:
    """Report whether the schedule is present, loaded, and hash-matched."""

    def execute(self) -> CommandResult:
        info = installer.status(last_maintain=read_state().get("last_maintain"))
        return CommandResult(success=True, output=self._render(info), metadata=self._metadata(info))

    @staticmethod
    def _render(info: ScheduleInfo) -> str:
        if not info.installed:
            return "schedule: not installed"
        lines = [
            f"schedule: {info.message}",
            f"artifact: {info.artifact_path}",
            f"present on disk: {info.present_on_disk}",
            f"hash matches: {info.hash_matches}",
            f"loaded: {info.loaded}",
            f"scheduled time: {info.scheduled_time or '(unknown)'}",
            f"last maintenance: {info.last_maintain or 'never'}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _metadata(info: ScheduleInfo) -> dict[str, object]:
        return {
            "installed": info.installed,
            "artifact": info.artifact_path,
            "present_on_disk": info.present_on_disk,
            "hash_matches": info.hash_matches,
            "loaded": info.loaded,
            "scheduled_time": info.scheduled_time,
            "last_maintain": info.last_maintain,
        }


class CommandScheduleUninstall:
    """Remove the scheduler artifact and the manifest entry."""

    def execute(self) -> CommandResult:
        res = installer.uninstall()
        return CommandResult(success=res.success, output=res.message, metadata={"artifact": res.artifact_path})

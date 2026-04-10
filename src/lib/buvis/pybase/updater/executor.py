"""Run upgrade command and re-exec the current process."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from subprocess import TimeoutExpired

from .detector import InstallerInfo
from .state import DEFAULT_STATE_DIR, append_log

__all__ = ["run_update"]

_UPGRADE_TIMEOUT = 120


def run_update(
    current: str,
    latest: str,
    installer: InstallerInfo,
    state_dir: Path | None = None,
) -> None:
    """Perform the upgrade silently, logging events to the updater state file.

    Args:
        current: Currently installed version string.
        latest: Newest available version string.
        installer: Detected installer info with upgrade command.
        state_dir: Directory for the updater state file. Defaults to ~/.config/buvis.
    """
    if state_dir is None:
        state_dir = DEFAULT_STATE_DIR

    if installer.upgrade_command is None:
        append_log(
            state_dir,
            "info",
            f"buvis-gems {latest} available (current: {current}); installer unknown, skipping upgrade",
        )
        return

    append_log(state_dir, "info", f"Updating buvis-gems {current} -> {latest} via {installer.method}")

    try:
        result = subprocess.run(
            installer.upgrade_command,
            capture_output=True,
            timeout=_UPGRADE_TIMEOUT,
        )
    except (TimeoutExpired, FileNotFoundError, OSError) as exc:
        append_log(state_dir, "error", f"Update failed: {exc}. Continuing with {current}.")
        return

    if result.returncode != 0:
        stderr_snippet = result.stderr.decode(errors="replace").strip()[:200]
        append_log(
            state_dir,
            "error",
            f"Update failed: {stderr_snippet}. Continuing with {current}.",
        )
        return

    append_log(state_dir, "info", f"Updated to {latest}, restarting")
    try:
        os.execvp(sys.argv[0], sys.argv)
    except OSError as exc:
        append_log(state_dir, "error", f"Restart failed: {exc}. Please re-run manually.")

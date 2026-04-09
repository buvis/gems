"""Run upgrade command and re-exec the current process."""

from __future__ import annotations

import os
import subprocess
import sys
from subprocess import TimeoutExpired

import click

from .detector import InstallerInfo

__all__ = ["run_update"]

_UPGRADE_TIMEOUT = 120


def run_update(current: str, latest: str, installer: InstallerInfo) -> None:
    """Perform the upgrade or print a notification.

    Args:
        current: Currently installed version string.
        latest: Newest available version string.
        installer: Detected installer info with upgrade command.
    """
    if installer.upgrade_command is None:
        click.echo(
            f"buvis-gems {latest} available (current: {current})",
            err=True,
        )
        return

    click.echo(f"Updating buvis-gems {current} -> {latest}...", err=True)

    try:
        result = subprocess.run(
            installer.upgrade_command,
            capture_output=True,
            timeout=_UPGRADE_TIMEOUT,
        )
    except (TimeoutExpired, FileNotFoundError, OSError) as exc:
        click.echo(f"Update failed: {exc}. Continuing with {current}.", err=True)
        return

    if result.returncode != 0:
        stderr_snippet = result.stderr.decode(errors="replace").strip()[:200]
        click.echo(
            f"Update failed: {stderr_snippet}. Continuing with {current}.",
            err=True,
        )
        return

    click.echo(f"Updated to {latest}, restarting...", err=True)
    try:
        os.execvp(sys.argv[0], sys.argv)
    except OSError as exc:
        click.echo(f"Restart failed: {exc}. Please re-run manually.", err=True)

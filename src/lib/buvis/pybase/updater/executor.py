"""Run upgrade command and re-exec the current process."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from subprocess import TimeoutExpired

from .detector import InstallerInfo
from .state import DEFAULT_STATE_DIR, append_log

__all__ = ["run_update", "run_update_interactive"]

_UPGRADE_TIMEOUT = 120
_MISE_WHERE_TIMEOUT = 10


def run_update(
    current: str,
    latest: str,
    installer: InstallerInfo,
    state_dir: Path | None = None,
) -> None:
    """Perform the upgrade silently, logging events to the updater state file.

    After a successful upgrade, this function re-execs the current process with
    the upgraded binary and does not return. If the re-exec cannot be performed,
    the process exits immediately because the current interpreter's cached files
    may have been replaced by the upgrade and continuing execution is unsafe.

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
    _reexec_or_exit(installer, state_dir)


def run_update_interactive(
    current: str,
    latest: str,
    installer: InstallerInfo,
    state_dir: Path | None = None,
) -> int:
    """Run the upgrade command with live output and return an exit code.

    Unlike ``run_update``, this does not re-exec: it is invoked from the
    ``--update`` flag's eager callback, which exits Click with the returned
    code immediately after.

    Returns 0 on success, 1 on any failure (subprocess error, nonzero exit,
    timeout, or an unknown installer passed by a defensive caller).
    """
    if state_dir is None:
        state_dir = DEFAULT_STATE_DIR

    if installer.upgrade_command is None:
        append_log(
            state_dir,
            "error",
            f"Cannot upgrade to {latest}: installer unknown.",
        )
        return 1

    print(f"Upgrading buvis-gems {current} \u2192 {latest} via {installer.method}...")
    append_log(
        state_dir,
        "info",
        f"Updating buvis-gems {current} \u2192 {latest} via {installer.method}",
    )

    try:
        result = subprocess.run(
            installer.upgrade_command,
            capture_output=False,
            timeout=_UPGRADE_TIMEOUT,
        )
    except (TimeoutExpired, FileNotFoundError, OSError) as exc:
        print(f"Update failed: {exc}")
        append_log(state_dir, "error", f"Update failed: {exc}")
        return 1

    if result.returncode != 0:
        print(f"Update failed: installer exited with code {result.returncode}")
        append_log(state_dir, "error", f"Update failed: exit code {result.returncode}")
        return 1

    print("Upgraded.")
    append_log(state_dir, "info", f"Upgraded buvis-gems to {latest}")
    return 0


def _reexec_or_exit(installer: InstallerInfo, state_dir: Path) -> None:
    """Replace the current process with the upgraded binary, or exit.

    Never returns. The current interpreter's loaded modules and open file handles
    may no longer match the files on disk after an upgrade, so the only safe
    options are to ``execvp`` into a fresh process or to exit immediately.
    """
    reexec_argv = _resolve_reexec_argv(installer)
    try:
        os.execvp(reexec_argv[0], reexec_argv)
    except OSError as exc:
        append_log(
            state_dir,
            "error",
            f"Restart failed: {exc}. Update applied; please re-run the command.",
        )
        sys.exit(0)


def _resolve_reexec_argv(installer: InstallerInfo) -> list[str]:
    """Return the argv to re-exec with after a successful upgrade.

    For installers that move the binary to a new version-specific directory on
    upgrade (``mise-pipx``), query the installer for the new root path and use
    that. For all other installers the binary stays at ``sys.argv[0]``.
    """
    argv = list(sys.argv)
    if installer.method == "mise-pipx":
        new_root = _query_mise_install_root()
        if new_root is not None:
            new_binary = new_root / "bin" / Path(argv[0]).name
            if new_binary.exists():
                return [str(new_binary), *argv[1:]]
    return argv


def _query_mise_install_root() -> Path | None:
    """Return the current mise install root for buvis-gems, or None on error."""
    try:
        result = subprocess.run(
            ("mise", "where", "pipx:buvis-gems"),
            capture_output=True,
            text=True,
            timeout=_MISE_WHERE_TIMEOUT,
        )
    except (FileNotFoundError, TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    path_text = result.stdout.strip()
    if not path_text:
        return None
    return Path(path_text)

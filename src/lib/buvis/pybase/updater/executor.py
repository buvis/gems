"""Run upgrade command and re-exec the current process."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from subprocess import TimeoutExpired

from buvis.pybase.adapters import console
from packaging.version import Version

from .detector import InstallerInfo
from .state import DEFAULT_STATE_DIR, append_log, clear_upgrade_failure, write_upgrade_failure

__all__ = ["REEXEC_ENV", "read_installed_version", "run_update", "run_update_interactive"]

# Set before re-exec so the restarted process skips the update check. An installer can exit 0
# without installing (e.g. mise hides releases younger than minimum_release_age); without this
# guard the restart sees the same "newer" PyPI release and re-execs forever.
REEXEC_ENV = "BUVIS_UPDATE_REEXEC"

_UPGRADE_TIMEOUT = 120
# --update is a foreground, user-initiated wait; bounded generously (not removed) so a
# genuinely hung installer is still reported rather than blocking forever.
_INTERACTIVE_UPGRADE_TIMEOUT = 1800
_MISE_WHERE_TIMEOUT = 10
_VERSION_TIMEOUT = 10
_VERSION_PATTERN = re.compile(r"version (\S+)")


def read_installed_version(installer: InstallerInfo) -> str | None:
    """Return the installed buvis-gems version as reported by a ``--version`` child.

    The child gets ``REEXEC_ENV=1``: ``--version`` runs the update check before
    the version option fires, so an unguarded child would start its own upgrade.

    Args:
        installer: Detected installer info, used to locate the upgraded binary.

    Returns:
        The installed version string, or None when it cannot be read.
    """
    try:
        argv0 = _resolve_reexec_argv(installer)[0]
        result = subprocess.run(
            [argv0, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT,
            env={**os.environ, REEXEC_ENV: "1"},
        )
        match = _VERSION_PATTERN.search(result.stdout)
        if match is None:
            return None
        Version(match.group(1))
        return match.group(1)
    except Exception:
        # Runs on every CLI start after an upgrade: any failure means "unverifiable", never a crash.
        return None


def _is_noop_upgrade(installed: str | None, current: str) -> bool:
    """True when verification ran and the installed version did not move past ``current``."""
    return installed is not None and Version(installed) <= Version(current)


def run_update(
    current: str,
    latest: str,
    installer: InstallerInfo,
    state_dir: Path | None = None,
) -> None:
    """Perform the upgrade silently, logging events to the updater state file.

    After a successful upgrade, this function re-execs the current process with
    the upgraded binary and does not return. If the re-exec cannot be performed,
    the process prints a user-visible failure message and exits with status 1,
    because the current interpreter's cached files may have been replaced by the
    upgrade and continuing execution is unsafe. When the installer exits 0 but the
    installed version did not move, it records ``latest`` for the upgrade back-off
    and returns without restarting.

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

    installed = read_installed_version(installer)
    if _is_noop_upgrade(installed, current):
        write_upgrade_failure(state_dir, latest)
        append_log(
            state_dir,
            "error",
            f"Upgrade to {latest} was a no-op: installer index may not offer it yet. Continuing with {current}.",
        )
        return
    if installed is None:
        append_log(state_dir, "warning", f"Could not verify the upgrade to {latest}; restarting once to pick it up")
    else:
        clear_upgrade_failure(state_dir)

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
    timeout, an installer that exits 0 without changing the installed version,
    or an unknown installer passed by a defensive caller).
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

    console.info(f"Upgrading buvis-gems {current} → {latest} via {installer.method}...")
    append_log(
        state_dir,
        "info",
        f"Updating buvis-gems {current} → {latest} via {installer.method}",
    )

    try:
        result = subprocess.run(
            installer.upgrade_command,
            capture_output=False,
            timeout=_INTERACTIVE_UPGRADE_TIMEOUT,
        )
    except (TimeoutExpired, FileNotFoundError, OSError) as exc:
        console.failure(f"Update failed: {exc}")
        append_log(state_dir, "error", f"Update failed: {exc}")
        return 1

    if result.returncode != 0:
        console.failure(f"Update failed: installer exited with code {result.returncode}")
        append_log(state_dir, "error", f"Update failed: exit code {result.returncode}")
        return 1

    if _is_noop_upgrade(read_installed_version(installer), current):
        message = f"Installer reported success but buvis-gems is still {current}; its index may not offer {latest} yet."
        console.failure(message)
        append_log(state_dir, "error", message)
        return 1

    console.success("Upgraded.")
    append_log(state_dir, "info", f"Upgraded buvis-gems to {latest}")
    return 0


def _reexec_or_exit(installer: InstallerInfo, state_dir: Path) -> None:
    """Replace the current process with the upgraded binary, or exit.

    Never returns. The current interpreter's loaded modules and open file handles
    may no longer match the files on disk after an upgrade, so the only safe
    options are to ``execvp`` into a fresh process or to report the failure
    through the console adapter and exit non-zero.
    """
    reexec_argv = _resolve_reexec_argv(installer)
    os.environ[REEXEC_ENV] = "1"
    try:
        os.execvp(reexec_argv[0], reexec_argv)
    except OSError as exc:
        message = f"Restart failed: {exc}. Update applied; please re-run the command."
        append_log(state_dir, "error", message)
        console.panic(message)


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

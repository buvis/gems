"""Platform-dispatched install/status/uninstall for the scheduler artifact.

macOS writes ``~/Library/LaunchAgents/net.buvis.klyreon.plist`` and bootstraps
it with ``launchctl bootstrap gui/<uid>``; Linux writes one marked crontab
fragment. Both record a manifest entry (``kind: schedule``) with the artifact
path, its content hash, the platform, the binary path, and the klyreon
version, reusing PRD C's manifest.

Every external boundary — ``launchctl``, ``crontab`` — goes through the two
tiny ``_run`` helpers so a test mocks exactly one place and the renderers stay
pure. An unsupported platform (Windows) fails with the manual equivalent named
and writes nothing. Re-runnable: install strips its own marked crontab lines or
boots out its own label before writing, so a reinstalled binary is one re-run.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from buvis.pybase.filesystem import atomic_write_text

from klyreon import __version__
from klyreon.assets.manifest import ManifestEntry, load_manifest, save_manifest
from klyreon.schedule.cron import MANAGED_MARKER, render_cron_line
from klyreon.schedule.launchd import LABEL, render_plist

__all__ = [
    "LABEL",
    "MANAGED_MARKER",
    "ScheduleInfo",
    "ScheduleResult",
    "UnsupportedPlatformError",
    "install",
    "status",
    "uninstall",
]

_KIND = "schedule"
_OPERATOR = "schedule"
_DEFAULT_HOUR = 3
_DEFAULT_MINUTE = 0


class UnsupportedPlatformError(RuntimeError):
    """Raised on a platform with no supported scheduler (e.g. Windows)."""


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    """What one install/uninstall did (success flag + human lines)."""

    success: bool
    message: str
    artifact_path: str | None = None


@dataclass(frozen=True, slots=True)
class ScheduleInfo:
    """What ``schedule status`` found."""

    installed: bool
    artifact_path: str | None = None
    present_on_disk: bool = False
    hash_matches: bool = False
    loaded: bool = False
    scheduled_time: str | None = None
    last_maintain: str | None = None
    platform: str | None = None
    message: str = ""


# --------------------------------------------------------------------------- #
# External boundaries (the only two places a test mocks)
# --------------------------------------------------------------------------- #


def _run(args: list[str], *, check: bool, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        input=input_text,
        check=check,
    )


def _launchctl(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return _run(["launchctl", *args], check=check)


def _crontab_read() -> str:
    """Return the current crontab text, or empty when none is installed."""
    completed = _run(["crontab", "-l"], check=False)
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _crontab_write(text: str) -> None:
    _run(["crontab", "-"], check=True, input_text=text if text.endswith("\n") or not text else text + "\n")


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _platform() -> str:
    return sys.platform


def _default_path_env() -> str:
    return os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _record_manifest(artifact_path: str, content_hash: str, moment: dt.datetime) -> None:
    manifest = load_manifest()
    manifest.upsert(
        ManifestEntry(
            kind=_KIND,
            operator=_OPERATOR,
            path=artifact_path,
            sha256=content_hash,
            klyreon_version=__version__,
            installed_at=moment.isoformat(),
        ),
    )
    save_manifest(manifest)


def _drop_manifest(artifact_path: str) -> None:
    manifest = load_manifest()
    manifest.remove_path(artifact_path)
    save_manifest(manifest)


def _schedule_entry_path() -> str | None:
    for entry in load_manifest().entries:
        if entry.kind == _KIND:
            return entry.path
    return None


def _schedule_entry_hash(artifact_path: str) -> str | None:
    entry = load_manifest().entry_for_path(artifact_path)
    return entry.sha256 if entry is not None else None


def _strip_managed_lines(crontab_text: str) -> str:
    """Return ``crontab_text`` with every klyreon-managed line removed."""
    kept = [line for line in crontab_text.splitlines() if MANAGED_MARKER not in line]
    body = "\n".join(kept).strip("\n")
    return body + "\n" if body else ""


# --------------------------------------------------------------------------- #
# install
# --------------------------------------------------------------------------- #


def install(
    *,
    binary: str,
    hour: int = _DEFAULT_HOUR,
    minute: int = _DEFAULT_MINUTE,
    path_env: str | None = None,
    now: dt.datetime | None = None,
) -> ScheduleResult:
    """Write the platform scheduler artifact and record it in the manifest.

    Re-runnable: boots out the existing label / strips existing managed lines
    first. An unsupported platform raises :class:`UnsupportedPlatformError`.
    """
    env_path = path_env if path_env is not None else _default_path_env()
    moment = now or _now()
    platform = _platform()
    if platform == "darwin":
        return _install_launchd(binary=binary, hour=hour, minute=minute, path_env=env_path, moment=moment)
    if platform.startswith("linux"):
        return _install_cron(binary=binary, hour=hour, minute=minute, path_env=env_path, moment=moment)
    msg = (
        f"no supported scheduler on platform {platform!r}. Install a scheduled task manually to run "
        f"'{binary} ingest; {binary} maintain' daily at {hour:02d}:{minute:02d}."
    )
    raise UnsupportedPlatformError(msg)


def _install_launchd(*, binary: str, hour: int, minute: int, path_env: str, moment: dt.datetime) -> ScheduleResult:
    plist = render_plist(binary=binary, hour=hour, minute=minute, path_env=path_env)
    plist_path = _plist_path()
    uid = os.getuid()

    # Boot out any prior instance of our own label before rewriting (re-run safe).
    _launchctl(["bootout", f"gui/{uid}/{LABEL}"], check=False)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(plist_path, plist)

    bootstrap = _launchctl(["bootstrap", f"gui/{uid}", str(plist_path)], check=False)
    if bootstrap.returncode != 0:
        # Do not record a manifest entry for an artifact that is not loaded.
        plist_path.unlink(missing_ok=True)
        detail = bootstrap.stderr.strip() or f"exit {bootstrap.returncode}"
        return ScheduleResult(
            success=False,
            message=(
                f"launchctl bootstrap failed ({detail}). Load it manually with: "
                f"launchctl bootstrap gui/{uid} {plist_path}"
            ),
            artifact_path=str(plist_path),
        )

    _record_manifest(str(plist_path), _sha256(plist), moment)
    return ScheduleResult(
        success=True,
        message=f"installed launchd agent {LABEL} at {hour:02d}:{minute:02d} ({plist_path})",
        artifact_path=str(plist_path),
    )


def _install_cron(*, binary: str, hour: int, minute: int, path_env: str, moment: dt.datetime) -> ScheduleResult:
    fragment = render_cron_line(binary=binary, hour=hour, minute=minute, path_env=path_env)
    existing = _strip_managed_lines(_crontab_read())
    new_crontab = (existing + fragment + "\n") if existing else (fragment + "\n")
    _crontab_write(new_crontab)
    # The artifact we hash and record is the fragment klyreon owns.
    artifact_path = "crontab:klyreon-managed"
    _record_manifest(artifact_path, _sha256(fragment), moment)
    return ScheduleResult(
        success=True,
        message=f"installed crontab entry at {hour:02d}:{minute:02d} (marked {MANAGED_MARKER})",
        artifact_path=artifact_path,
    )


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #


def status(*, last_maintain: str | None = None) -> ScheduleInfo:
    """Report the installed schedule: present, loaded, hash-matched, scheduled time."""
    artifact_path = _schedule_entry_path()
    if artifact_path is None:
        return ScheduleInfo(installed=False, message="no schedule installed")

    platform = _platform()
    if platform == "darwin" or artifact_path.endswith(".plist"):
        return _status_launchd(artifact_path, last_maintain)
    return _status_cron(artifact_path, last_maintain)


def _status_launchd(artifact_path: str, last_maintain: str | None) -> ScheduleInfo:
    path = Path(artifact_path)
    present = path.is_file()
    hash_matches = False
    scheduled_time = None
    if present:
        on_disk = path.read_text(encoding="utf-8")
        hash_matches = _sha256(on_disk) == _schedule_entry_hash(artifact_path)
        scheduled_time = _plist_time(on_disk)
    listed = _launchctl(["list", LABEL], check=False)
    loaded = listed.returncode == 0
    message = _status_message(present, hash_matches, loaded)
    return ScheduleInfo(
        installed=True,
        artifact_path=artifact_path,
        present_on_disk=present,
        hash_matches=hash_matches,
        loaded=loaded,
        scheduled_time=scheduled_time,
        last_maintain=last_maintain,
        platform="darwin",
        message=message,
    )


def _status_cron(artifact_path: str, last_maintain: str | None) -> ScheduleInfo:
    crontab = _crontab_read()
    managed = [line for line in crontab.splitlines() if MANAGED_MARKER in line]
    loaded = bool(managed)
    # The "artifact on disk" for cron is the managed fragment itself.
    present = loaded
    hash_matches = False
    scheduled_time = None
    if managed:
        fragment = "\n".join(managed)
        # Rebuild the recorded fragment shape (PATH line + schedule line) to compare.
        hash_matches = _sha256(_canonical_cron_fragment(managed)) == _schedule_entry_hash(artifact_path)
        scheduled_time = _cron_time(managed)
        _ = fragment
    message = _status_message(present, hash_matches, loaded)
    return ScheduleInfo(
        installed=True,
        artifact_path=artifact_path,
        present_on_disk=present,
        hash_matches=hash_matches,
        loaded=loaded,
        scheduled_time=scheduled_time,
        last_maintain=last_maintain,
        platform="linux",
        message=message,
    )


def _status_message(present: bool, hash_matches: bool, loaded: bool) -> str:
    if not present:
        return "schedule recorded but its artifact is missing on disk"
    if not hash_matches:
        return "schedule artifact was edited since install (hash mismatch); not rewriting it"
    if not loaded:
        return "schedule artifact present and unmodified but not loaded by the scheduler"
    return "schedule present, loaded, and matching its recorded hash"


def _canonical_cron_fragment(managed_lines: list[str]) -> str:
    """Rebuild the two-line fragment in recorded order (PATH line, then schedule)."""
    path_lines = [ln for ln in managed_lines if ln.startswith("PATH=")]
    other = [ln for ln in managed_lines if not ln.startswith("PATH=")]
    return "\n".join(path_lines + other)


def _plist_time(plist_text: str) -> str | None:
    import re

    hour = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", plist_text)
    minute = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", plist_text)
    if hour and minute:
        return f"{int(hour.group(1)):02d}:{int(minute.group(1)):02d}"
    return None


def _cron_time(managed_lines: list[str]) -> str | None:
    for line in managed_lines:
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{int(parts[1]):02d}:{int(parts[0]):02d}"
    return None


# --------------------------------------------------------------------------- #
# uninstall
# --------------------------------------------------------------------------- #


def uninstall() -> ScheduleResult:
    """Remove the artifact and the manifest entry. Idempotent."""
    artifact_path = _schedule_entry_path()
    if artifact_path is None:
        return ScheduleResult(success=True, message="no schedule installed; nothing to uninstall")

    platform = _platform()
    if platform == "darwin" or artifact_path.endswith(".plist"):
        uid = os.getuid()
        _launchctl(["bootout", f"gui/{uid}/{LABEL}"], check=False)
        Path(artifact_path).unlink(missing_ok=True)
    else:
        stripped = _strip_managed_lines(_crontab_read())
        _crontab_write(stripped)

    _drop_manifest(artifact_path)
    return ScheduleResult(success=True, message=f"uninstalled schedule ({artifact_path})", artifact_path=artifact_path)

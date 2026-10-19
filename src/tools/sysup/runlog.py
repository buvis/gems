from __future__ import annotations

import contextlib
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.adapters import console
from buvis.pybase.result import FatalError

if TYPE_CHECKING:
    from typing import TextIO

__all__ = ["RunLog", "append_step", "logs_dir", "open_run_log", "prune"]

_NAME_RE = re.compile(r"^\d{8}T\d{6}Z(-\d+)?\.log$")
_KEEP = 9  # files kept BEFORE this run's file is created (10 total after)


def logs_dir() -> Path:
    """``$XDG_STATE_HOME/sysup/logs``, falling back to ``~/.local/state/sysup/logs``."""
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "sysup" / "logs"


@dataclass
class RunLog:
    """An open, exclusively-created run-log file. Not reused across runs."""

    path: Path
    _handle: TextIO


def _is_disposable_log(entry: Path) -> bool:
    """True only for a regular file whose basename matches the run-log naming scheme."""
    if not _NAME_RE.match(entry.name):
        return False
    try:
        info = os.lstat(entry)
    except FileNotFoundError:
        return False
    return stat.S_ISREG(info.st_mode)


def _list_candidates(directory: Path) -> list[tuple[float, str, Path]] | None:
    """List run-log prune candidates with their ``st_mtime``, or ``None`` if ``directory`` is missing.

    Reports (via ``console.warning``) and skips any entry whose name does not
    match the run-log scheme, that vanished between listing and stat, or that
    is not a regular file. Raises ``FatalError`` on any other stat failure.
    """
    try:
        entries = list(directory.iterdir())
    except FileNotFoundError:
        return None
    except OSError as exc:
        msg = f"could not list run-log directory {directory}: {exc}"
        raise FatalError(msg) from exc

    candidates: list[tuple[float, str, Path]] = []
    for entry in entries:
        if not _NAME_RE.match(entry.name):
            console.warning(f"run-log prune: skipping {entry} (name does not match run-log scheme)")
            continue
        try:
            info = os.lstat(entry)
        except FileNotFoundError:
            continue
        except OSError as exc:
            msg = f"could not stat run-log candidate {entry}: {exc}"
            raise FatalError(msg) from exc
        if not stat.S_ISREG(info.st_mode):
            console.warning(f"run-log prune: skipping {entry} (not a regular file)")
            continue
        candidates.append((info.st_mtime, entry.name, entry))
    return candidates


def prune(directory: Path, *, keep: int = _KEEP) -> None:
    """Delete oldest matching log files beyond ``keep``, oldest-first.

    Premise re-checked per file immediately before each deletion using
    ``os.lstat(path).st_mode`` and ``stat.S_ISREG(...)`` — NOT ``Path.is_file()``,
    which follows symlinks and would let a symlink named like a log (pointing
    anywhere, including outside ``directory``) pass the check and be deleted.
    ``lstat`` reports the link itself, so a symlink always fails ``S_ISREG``
    and is skipped, never followed. The basename must also match ``_NAME_RE``.
    A mismatch (wrong type or wrong name) is reported (not raised) via
    ``console.warning`` and skipped, both at listing time and again
    immediately before deletion. Ordering: by ``st_mtime`` (from the listing
    ``lstat``), filename as tie-breaker. Missing ``directory`` is a no-op. A
    candidate that vanishes between the initial listing and its re-check
    (``FileNotFoundError`` from either the pre-deletion ``os.lstat`` or
    ``os.unlink``) is treated as already-pruned, not an error. Raises
    ``FatalError`` wrapping any OTHER ``OSError`` hit during listing or
    deletion, with the offending path in the message, after attempting no
    further deletions this call.
    """
    candidates = _list_candidates(directory)
    if candidates is None:
        return

    candidates.sort(key=lambda item: (item[0], item[1]))
    overflow = len(candidates) - keep
    if overflow <= 0:
        return

    for _, _, path in candidates[:overflow]:
        try:
            still_disposable = _is_disposable_log(path)
        except OSError as exc:
            msg = f"could not stat run-log candidate {path}: {exc}"
            raise FatalError(msg) from exc
        if not still_disposable:
            console.warning(f"run-log prune: skipping {path} (no longer a disposable run log)")
            continue
        try:
            os.unlink(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            msg = f"could not delete run-log {path}: {exc}"
            raise FatalError(msg) from exc


def open_run_log(start: datetime, plan_names: list[str]) -> RunLog:
    """Create today's run-log file exclusively and write its header.

    Resolves ``logs_dir()``, creates it (``mkdir(parents=True, exist_ok=True)``),
    does NOT call :func:`prune` itself (the caller prunes first). Base name:
    ``start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".log"``. On a
    same-second collision (``FileExistsError`` from exclusive open), retries
    with ``-1``, ``-2``, ... suffixes before the extension, first available
    wins. Opens with ``os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)``
    then wraps in a text handle — never ``os.O_TRUNC``, so an unexpected
    existing non-matching file is never silently overwritten (it just forces
    the next suffix). Writes the header:

    ```
    sysup run <start ISO-8601 UTC, seconds precision>
    plan: <comma-joined plan_names, or "(empty)">
    ```

    followed by a blank line, then ``handle.flush()`` and
    ``os.fsync(handle.fileno())`` (same durability pattern as
    ``pybase.filesystem.atomic_write_text``, applied here to an append-mode
    handle rather than a tempfile-then-replace), and returns the open
    ``RunLog``. Raises ``FatalError`` wrapping any ``OSError`` from directory
    creation or the exclusive-create retry loop, WITH THE ATTEMPTED PATH in
    the message (e.g. ``f"could not create run log {path}: {exc}"``). If the
    exclusive create itself succeeds but the header write or flush then
    fails: if the text-handle wrap (``os.fdopen(fd, ...)``) itself raised,
    the raw ``fd`` is closed with ``os.close(fd)``; if wrapping succeeded and
    the write/flush on the WRAPPED handle then failed, that handle (not the
    raw ``fd``, which the wrapper now owns) is closed with the handle's own
    ``.close()`` instead — both suppress any secondary close error, re-raising
    the original ``FatalError`` naming the just-created (but now incomplete
    and closed) path.
    """
    directory = logs_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        msg = f"could not create run log directory {directory}: {exc}"
        raise FatalError(msg) from exc

    base = start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fd, path = _create_exclusive(directory, base)
    handle = _write_header(fd, path, start, plan_names)
    return RunLog(path=path, _handle=handle)


def _create_exclusive(directory: Path, base: str) -> tuple[int, Path]:
    """Exclusively create ``<base>.log``, retrying ``-1``, ``-2``, ... on collision."""
    fd: int | None = None
    path: Path | None = None
    suffix = 0
    last_error: OSError | None = None
    while suffix <= 10_000:
        name = f"{base}.log" if suffix == 0 else f"{base}-{suffix}.log"
        candidate = directory / name
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            suffix += 1
            continue
        except OSError as exc:
            last_error = exc
            break
        path = candidate
        break

    if fd is None or path is None:
        detail = last_error if last_error is not None else "no available filename"
        msg = f"could not create run log {directory / (base + '.log')}: {detail}"
        raise FatalError(msg)
    return fd, path


def _write_header(fd: int, path: Path, start: datetime, plan_names: list[str]) -> TextIO:
    """Wrap ``fd`` in a text handle and write/flush/fsync the run-log header."""
    try:
        handle = os.fdopen(fd, "w", encoding="utf-8")
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.close(fd)
        msg = f"could not create run log {path}: {exc}"
        raise FatalError(msg) from exc

    try:
        stamp = start.astimezone(timezone.utc).isoformat(timespec="seconds")
        plan = ", ".join(plan_names) if plan_names else "(empty)"
        handle.write(f"sysup run {stamp}\nplan: {plan}\n\n")
        handle.flush()
        os.fsync(handle.fileno())
    except OSError as exc:
        msg = f"could not create run log {path} (incomplete): {exc}"
        with contextlib.suppress(OSError):
            handle.close()
        raise FatalError(msg) from exc
    return handle


def append_step(
    log: RunLog,
    entry: str,
    descriptor: str,
    *,
    captured: bool,
    status: str,
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    timeout_s: float | None = None,
) -> None:
    """Append one completed step's section, then ``handle.flush()`` and
    ``os.fsync(handle.fileno())``. Section marker format: see :func:`_format_section`.

    Raises ``FatalError`` wrapping any ``OSError`` from the write or flush,
    WITH ``log.path`` in the message. Performs no retry and leaves previously
    flushed sections intact (the file is not truncated or reopened on error).
    Does NOT close ``log`` on failure — the caller's ``finally`` still calls
    :func:`close` exactly once regardless of how the generator unwound.
    """
    section = _format_section(
        entry,
        descriptor,
        captured=captured,
        status=status,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        timeout_s=timeout_s,
    )
    try:
        log._handle.write(section)
        log._handle.flush()
        os.fsync(log._handle.fileno())
    except OSError as exc:
        msg = f"could not write run log {log.path} (incomplete): {exc}"
        raise FatalError(msg) from exc


def _format_section(
    entry: str,
    descriptor: str,
    *,
    captured: bool,
    status: str,
    exit_code: int | None,
    stdout: str,
    stderr: str,
    timed_out: bool,
    timeout_s: float | None,
) -> str:
    """Render one ``=== ... ===`` section marker plus its body.

    ``descriptor`` is the argv joined with spaces (captured/timeout sections)
    or the ``use:`` capability name / interactive argv string (not-captured
    sections). Section markers, exactly:

    - captured, no timeout: ``=== <entry>: <descriptor> (exit <exit_code>) ===``
      followed by ``stdout`` written verbatim (preserving its own internal
      newlines, no per-line transformation), then a single ``\\n``, then
      ``stderr`` written verbatim the same way — neither stream gets its own
      sub-header; a trailing blank line after both.
    - timed out (``timed_out=True``): ``=== <entry>: <descriptor> (timed out after <timeout_s>s) ===``
      followed by whatever ``stdout``/``stderr`` partial text is available
      (empty string if none) — never invents an exit code.
    - not captured (``captured=False``): ``=== <entry>: <descriptor> (<status>, not captured) ===``
      with no stdout/stderr section.
    """
    if timed_out:
        header = f"=== {entry}: {descriptor} (timed out after {timeout_s}s) ===\n"
        body = f"{stdout}\n{stderr}\n\n"
    elif not captured:
        header = f"=== {entry}: {descriptor} ({status}, not captured) ===\n\n"
        body = ""
    else:
        header = f"=== {entry}: {descriptor} (exit {exit_code}) ===\n"
        body = f"{stdout}\n{stderr}\n\n"
    return header + body


def close(log: RunLog) -> None:
    """Close the underlying handle. Raises ``FatalError`` wrapping ``OSError``,
    with ``log.path`` in the message, same rationale as :func:`append_step`."""
    try:
        log._handle.close()
    except OSError as exc:
        msg = f"could not close run log {log.path} (incomplete): {exc}"
        raise FatalError(msg) from exc

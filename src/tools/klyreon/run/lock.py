"""Single-instance guard: two klyreon runs never touch one vault at once.

A non-blocking ``fcntl.flock`` on
``$XDG_STATE_HOME/klyreon/<sha256(root)[:12]>.lock``, held for the run and
released in ``finally`` -- so ``KeyboardInterrupt`` and every other
``BaseException`` release it, and process death releases it at the kernel level
(the claim-release invariant). This is the PRD "Single-instance guard" feature;
PRD D reuses this module.

An invocation that cannot take the lock raises :class:`LockBusyError`: the CLI
turns that into an info line and exit 0, because overlapping cron ticks are
expected, not an error.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = ["LockBusyError", "lock_path", "vault_lock"]


class LockBusyError(RuntimeError):
    """Raised when another klyreon run already holds the vault lock."""


def _state_dir() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "klyreon"


def lock_path(root: Path) -> Path:
    """Return the lock file path for the vault at ``root``.

    The name is ``<sha256(resolved-root)[:12]>.lock`` so two vaults never share
    a lock and the name does not leak the path.
    """
    digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    return _state_dir() / f"{digest}.lock"


@contextmanager
def vault_lock(root: Path) -> Iterator[Path]:
    """Hold the vault lock for the duration of the ``with`` block.

    Yields the lock-file path. Releases in ``finally`` on any exit, normal or
    exceptional.

    Raises:
        LockBusyError: when another process already holds the lock.
    """
    path = lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open (not truncate) so a concurrent holder's advisory lock is what gates
    # us, never the file content. The fd is the lock's lifetime.
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            msg = f"another klyreon run already holds the vault lock: {path}"
            raise LockBusyError(msg) from exc
        try:
            yield path
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)

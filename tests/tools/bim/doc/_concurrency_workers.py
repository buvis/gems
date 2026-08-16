"""Worker functions for the bim doc concurrency tests.

These functions run in separate processes spawned by the tests. They live
in a non-``test_`` module on purpose: pytest's spawn-method workers re-
import the target module before invoking the function, and re-importing a
``test_*.py`` file would re-trigger pytest collection and deadlock against
the very fcntl/SQLite resources we are trying to test.

Module name is underscore-prefixed so pytest's collector ignores it.
"""

from __future__ import annotations

import multiprocessing as mp
from datetime import timedelta
from pathlib import Path


def register_issuer_worker(
    registry_path_str: str,
    lock_path_str: str,
    slug: str,
    display_name: str,
    out_queue: mp.queues.Queue,
    barrier: mp.synchronize.Barrier,
) -> None:
    """Try to register ``slug`` against the issuer registry under flock.

    All workers wait at ``barrier`` so they race into ``register_issuer``
    together. Exactly one worker should succeed; the others should observe
    the slug as already-registered and raise ValueError. Result strings:
    ``"ok"`` on success, ``"already_registered"`` on the expected loser
    path, or ``"error: <repr>"`` on anything else.
    """
    from bim.commands.doc.shared.issuers import register_issuer

    barrier.wait()
    try:
        register_issuer(
            registry_path=Path(registry_path_str),
            lock_path=Path(lock_path_str),
            slug=slug,
            display_name=display_name,
        )
        out_queue.put("ok")
    except ValueError as exc:
        msg = str(exc)
        if "already registered" in msg or "is reserved" in msg:
            out_queue.put("already_registered")
        else:
            out_queue.put(f"error: {exc!r}")
    except Exception as exc:
        # Bare Exception catch is intentional: the child process must surface
        # any failure mode through ``out_queue`` so the parent test can fail
        # with a useful message instead of hanging on a missing queue item.
        out_queue.put(f"error: {exc!r}")


def claim_worker(
    db_path_str: str,
    sha256: str,
    out_queue: mp.queues.Queue,
    barrier: mp.synchronize.Barrier,
) -> None:
    """Open the state DB and call ``claim(sha256)``.

    All workers wait at ``barrier`` so they race into the SQL INSERT
    together. Exactly one worker should observe ``rowcount == 1`` (True);
    the rest should see ``False``. Result strings: ``"true"`` /
    ``"false"`` / ``"error: <repr>"``.
    """
    from bim.commands.doc.shared.state_db import StateDB

    barrier.wait()
    try:
        db = StateDB.open(Path(db_path_str))
        try:
            won = db.claim(sha256)
            out_queue.put("true" if won else "false")
        finally:
            db.connection.close()
    except Exception as exc:
        # Same diagnostic-surface rationale as register_issuer_worker above.
        out_queue.put(f"error: {exc!r}")


def reclaiming_claim_worker(
    db_path_str: str,
    sha256: str,
    max_age_seconds: float,
    out_queue: mp.queues.Queue,
    barrier: mp.synchronize.Barrier,
) -> None:
    """Open the state DB and call ``claim(sha256, max_age=...)``.

    Same race as ``claim_worker``, but every worker meets a claim already
    older than ``max_age_seconds``, so they all take the reclaim branch
    instead of the plain insert. Exactly one may still win. Result strings:
    ``"true"`` / ``"false"`` / ``"error: <repr>"``.
    """
    from bim.commands.doc.shared.state_db import StateDB

    barrier.wait()
    try:
        db = StateDB.open(Path(db_path_str))
        try:
            won = db.claim(sha256, max_age=timedelta(seconds=max_age_seconds))
            out_queue.put("true" if won else "false")
        finally:
            db.connection.close()
    except Exception as exc:
        # Same diagnostic-surface rationale as register_issuer_worker above.
        out_queue.put(f"error: {exc!r}")

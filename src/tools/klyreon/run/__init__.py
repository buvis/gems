"""Run machinery shared by ``ingest`` and (PRD D) ``maintain``.

Phase 0 ships the single-instance lock; Phase 1 adds the staging area and
Phase 2 the trail writer. Re-exports are added as each lands so callers import
from ``klyreon.run`` regardless of which module owns a symbol.
"""

from __future__ import annotations

from klyreon.run.lock import LockBusyError, vault_lock

__all__ = ["LockBusyError", "vault_lock"]

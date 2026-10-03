"""Autonomous maintenance (PRD 00077).

The idempotent, cron-safe sweep over the whole vault: lint (reuses PRD A's
``validate_vault``), rule-driven lifecycle and assent transitions, MOC
membership reconciliation, and prune-candidate detection. Every rule is a pure
function of vault state, so a second run finds nothing to do and no LLM is
ever called.

Re-exports are added as each module lands so callers import from
``klyreon.maintain`` regardless of which module owns a symbol.
"""

from __future__ import annotations

from klyreon.maintain.graph import VaultGraph
from klyreon.maintain.moc_sync import MocSyncPlan, apply_moc_sync, plan_moc_sync
from klyreon.maintain.prune import PruneCandidate, find_candidates, prune
from klyreon.maintain.rules import Transition, plan_assent, plan_lifecycle
from klyreon.maintain.sweep import MaintainResult, run_maintain

__all__ = [
    "MaintainResult",
    "MocSyncPlan",
    "PruneCandidate",
    "Transition",
    "VaultGraph",
    "apply_moc_sync",
    "find_candidates",
    "plan_assent",
    "plan_lifecycle",
    "plan_moc_sync",
    "prune",
    "run_maintain",
]

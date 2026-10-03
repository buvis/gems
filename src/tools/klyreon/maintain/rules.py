"""Pure transition planners: a zettel plus the graph to a planned change.

No I/O. Each planner returns a :class:`Transition` or ``None`` (nothing to do).
Every rule is mechanical and a function of vault state alone, so a second
sweep over an applied vault plans nothing — the idempotence the PRD requires.

The rules (spec 7.3 lifecycle, 7.2 assent, discovery Q19):

- Lifecycle ``fleeting -> literature`` when the zettel cites at least one
  source AND carries at least one link in either direction.
- Lifecycle ``literature -> evergreen`` when at least two DISTINCT source
  documents back it (own ``sources`` plus the ``sources`` of its supporters).
- Assent ``tentative -> accepted`` when two or more distinct source documents
  corroborate it, counted across its supporters' sources and EXCLUDING its own.
  Any open ``disagreement`` doubt (on it or targeting it) holds it in place.

Promotion never resets ``processed`` and maintain never writes ``rejected``.
"""

from __future__ import annotations

from dataclasses import dataclass

from klyreon.maintain.graph import VaultGraph
from klyreon.spec.enums import Assent, Lifecycle
from klyreon.spec.model import Document

__all__ = ["Transition", "plan_assent", "plan_lifecycle"]

_CORROBORATION_THRESHOLD = 2


@dataclass(frozen=True, slots=True)
class Transition:
    """One planned field change on a zettel.

    Attributes:
        path: The zettel's vault-relative path.
        field: The frontmatter field to change (``lifecycle`` or ``assent``).
        old: The current value.
        new: The value to write.
        reason: A short, human-readable justification for the trail.
    """

    path: str
    field: str
    old: str
    new: str
    reason: str


def plan_lifecycle(zettel: Document, graph: VaultGraph) -> Transition | None:
    """Plan a lifecycle promotion for ``zettel``, or ``None`` when none applies.

    Only concept zettels (those carrying a ``lifecycle``) are promoted. The
    ladder is one step per sweep: a ``fleeting`` zettel that also qualifies for
    ``evergreen`` moves to ``literature`` first and reaches ``evergreen`` on the
    next sweep, keeping every transition auditable as its own commit.
    """
    current = zettel.get("lifecycle")
    if not isinstance(current, str):
        return None
    path = zettel.path

    if current == Lifecycle.FLEETING.value:
        has_source = bool(graph.own_sources(path))
        has_link = graph.outbound_count(path) > 0 or bool(graph.inbound(path))
        if has_source and has_link:
            return Transition(
                path=path,
                field="lifecycle",
                old=current,
                new=Lifecycle.LITERATURE.value,
                reason="cites a source and carries a link: earned a place in the graph",
            )
        return None

    if current == Lifecycle.LITERATURE.value:
        distinct = graph.corroborating_sources(path, include_own=True)
        if len(distinct) >= _CORROBORATION_THRESHOLD:
            return Transition(
                path=path,
                field="lifecycle",
                old=current,
                new=Lifecycle.EVERGREEN.value,
                reason=f"backed by {len(distinct)} distinct source documents",
            )
    return None


def plan_assent(zettel: Document, graph: VaultGraph) -> Transition | None:
    """Plan an assent promotion for ``zettel``, or ``None`` when none applies.

    ``tentative -> accepted`` only, and only when two or more distinct source
    documents OTHER than the zettel's own corroborate it. An open disagreement
    doubt holds it. maintain never writes ``rejected``.
    """
    current = zettel.get("assent")
    if current != Assent.TENTATIVE.value:
        return None
    path = zettel.path

    if graph.open_disagreements(path):
        return None

    corroborating = graph.corroborating_sources(path, include_own=False)
    if len(corroborating) >= _CORROBORATION_THRESHOLD:
        return Transition(
            path=path,
            field="assent",
            old=Assent.TENTATIVE.value,
            new=Assent.ACCEPTED.value,
            reason=f"corroborated by {len(corroborating)} distinct source documents",
        )
    return None

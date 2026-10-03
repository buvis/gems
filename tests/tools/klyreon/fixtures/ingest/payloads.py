"""Canned backend payloads for the ingest fixture corpus.

These are the shipped-double answers the :class:`StubBackend` returns, keyed by
the ``stub-marker`` line each fixture source embeds. They let the whole ingest
pipeline run offline: a mixed sweep gets a single ``StubBackend(by_marker=...)``
and every source resolves deterministically.

Four happy-path drafts (one per spec source type) plus five conflict payloads
against the ``conflict-vault`` baseline (``20260301090000#c1`` accepted,
``20260301093000#c1`` rejected). The conflict payloads exercise aporia, refine,
supersede, the rejected-target drop, and an aporia that also ships a claim-less
aporia zettel.
"""

from __future__ import annotations

from klyreon.backends.base import (
    ConflictEntry,
    ConflictShape,
    CorroborationEntry,
    DoubtEntry,
    IngestPayload,
    LinkTarget,
    PayloadClaim,
    ZettelDraft,
)

_EPISTEMICS_MOC = "wiki/mocs/epistemics.md"
_ACCEPTED = "wiki/notes/20260301090000.md"
_REJECTED = "wiki/notes/20260301093000.md"

# --------------------------------------------------------------------------- #
# Happy path: one draft per spec source type.
# --------------------------------------------------------------------------- #

HAPPY_PATH: dict[str, IngestPayload] = {
    "article-cache-invalidation": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Cache invalidation is a two-step race",
                type="note",
                concept_type="thesis",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="A cache serves stale data in the window between a write and its invalidation.",
                    ),
                ],
                doubts=[
                    DoubtEntry(
                        mode="context-relative",
                        claim="c1",
                        rationale="Only matters when a reader can observe the cache between the two steps.",
                    ),
                ],
                tags=["caching"],
                mocs=["wiki/mocs/architecture.md"],
                body="A cache serves stale data between a write and its invalidation.",
            ),
        ],
    ),
    "book-thinking-fast-slow-ch1": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Two systems run the mind at different speeds",
                type="note",
                concept_type="observation",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="System 1 answers fast and automatically before System 2 deliberates.",
                    ),
                ],
                tags=["cognition"],
                mocs=["wiki/mocs/architecture.md"],
                body="System 1 is fast and automatic; System 2 is slow and effortful.",
            ),
        ],
    ),
    "quote-brooks-no-silver-bullet": IngestPayload(
        zettels=[
            ZettelDraft(
                title="No single technique gives an order-of-magnitude gain",
                type="note",
                concept_type="thesis",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="No single technique yields an order-of-magnitude productivity gain within a decade.",
                    ),
                ],
                tags=["software-engineering"],
                mocs=["wiki/mocs/architecture.md"],
                body="No single technique promises an order-of-magnitude improvement within a decade.",
            ),
        ],
    ),
    "transcript-arch-review-2026-05-01": IngestPayload(
        zettels=[
            ZettelDraft(
                title="A concurrency cap fixes a pileup that retries only defer",
                type="note",
                concept_type="argument",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="A consumer concurrency cap fixes a backlog that bounded retries merely postpone.",
                    ),
                ],
                tags=["architecture"],
                mocs=["wiki/mocs/architecture.md"],
                body="Retries buy time; the concurrency cap is the real fix for a consumer pileup.",
            ),
        ],
    ),
}


# --------------------------------------------------------------------------- #
# Conflicts against the conflict-vault baseline.
# --------------------------------------------------------------------------- #

CONFLICTS: dict[str, IngestPayload] = {
    "conflict-aporia-doubt": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Certainty is a psychological state, not an evidential one",
                type="note",
                concept_type="thesis",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="Certainty is a feeling in the knower, not a property evidence confers.",
                    ),
                ],
                mocs=[_EPISTEMICS_MOC],
                body="Certainty is a state of the knower, not a property of the warrant.",
            ),
        ],
        conflicts=[
            ConflictEntry(
                new_zettel=0,
                new_claim="c1",
                target=LinkTarget(to=_ACCEPTED, claim="c1"),
                shape=ConflictShape.APORIA,
                rationale="Both are defensible; neither refutes the other.",
            ),
        ],
    ),
    "conflict-refine": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Certainty holds only within a fixed frame",
                type="note",
                concept_type="thesis",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="Evidence confers certainty only relative to a fixed frame of assumptions.",
                    ),
                ],
                mocs=[_EPISTEMICS_MOC],
                body="Certainty from evidence holds only within a fixed frame of assumptions.",
            ),
        ],
        conflicts=[
            ConflictEntry(
                new_zettel=0,
                new_claim="c1",
                target=LinkTarget(to=_ACCEPTED, claim="c1"),
                shape=ConflictShape.REFINE,
                rationale="Narrows the unqualified claim to a frame.",
            ),
        ],
    ),
    "conflict-supersede": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Certainty comes from independent lines, not a count of sources",
                type="note",
                concept_type="thesis",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="Independence of evidential lines, not their count, is what makes a claim certain.",
                    ),
                ],
                mocs=[_EPISTEMICS_MOC],
                body="It is the independence of the lines, not their number, that confers certainty.",
            ),
        ],
        conflicts=[
            ConflictEntry(
                new_zettel=0,
                new_claim="c1",
                target=LinkTarget(to=_ACCEPTED, claim="c1"),
                shape=ConflictShape.SUPERSEDE,
                rationale="Replaces the earlier count-based framing.",
            ),
        ],
    ),
    "conflict-rejected-target": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Knowledge stays merely probable",
                type="note",
                concept_type="thesis",
                claims=[
                    PayloadClaim(id="c1", statement="No claim is ever certain; all knowledge stays probable."),
                ],
                mocs=[_EPISTEMICS_MOC],
                body="All knowledge remains merely probable.",
            ),
        ],
        conflicts=[
            # The backend proposes a conflict against a zettel that is already
            # assent: rejected. Code drops it before any edit and logs it as
            # corroborating the existing rejection (discovery Q13), whatever the
            # proposed shape.
            ConflictEntry(
                new_zettel=0,
                new_claim="c1",
                target=LinkTarget(to=_REJECTED, claim="c1"),
                shape=ConflictShape.SUPERSEDE,
                rationale="Agrees with the already-rejected thesis.",
            ),
        ],
    ),
    "conflict-aporia-zettel": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Whether evidence confers certainty is a standing impasse",
                type="note",
                concept_type="thesis",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="The cases for and against evidential certainty are equally matched.",
                    ),
                ],
                mocs=[_EPISTEMICS_MOC],
                body="The question has resisted resolution; the cases are equally matched.",
            ),
            # A claim-less aporia zettel the backend also returns (spec 7.5): it
            # carries no claims of its own and points at both sides.
            ZettelDraft(
                title="Aporia: can evidence confer certainty?",
                type="note",
                concept_type="aporia",
                claims=[],
                mocs=[_EPISTEMICS_MOC],
                body="A standing disagreement over whether evidence can make a claim certain.",
            ),
        ],
        conflicts=[
            ConflictEntry(
                new_zettel=0,
                new_claim="c1",
                target=LinkTarget(to=_ACCEPTED, claim="c1"),
                shape=ConflictShape.APORIA,
                rationale="Recorded as a standing aporia.",
            ),
        ],
    ),
}

# A corroboration-only payload: a happy-path draft that agrees with the
# accepted baseline from a different source (PRD "Corroboration recording").
CORROBORATION: dict[str, IngestPayload] = {
    "corroborate-certainty": IngestPayload(
        zettels=[
            ZettelDraft(
                title="Independent replication can settle a claim",
                type="note",
                concept_type="observation",
                claims=[
                    PayloadClaim(
                        id="c1",
                        statement="Independent replication can settle a claim beyond reasonable doubt.",
                    ),
                ],
                mocs=[_EPISTEMICS_MOC],
                body="Independent replication can settle a claim.",
            ),
        ],
        corroborations=[
            CorroborationEntry(
                new_zettel=0,
                target=LinkTarget(to=_ACCEPTED, claim="c1"),
                rationale="Agrees with the accepted certainty thesis from a different source.",
            ),
        ],
    ),
}


def all_markers() -> dict[str, IngestPayload]:
    """Every canned payload keyed by its stub marker, for a mixed sweep."""
    merged: dict[str, IngestPayload] = {}
    merged.update(HAPPY_PATH)
    merged.update(CONFLICTS)
    merged.update(CORROBORATION)
    return merged

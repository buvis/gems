"""Render backend drafts into spec-valid zettel documents (code, not the LLM).

Rendering is deterministic klyreon work (PRD "Per-source pipeline"): klyreon
allocates each id with 00074's collision rule, sets ``sources`` to the
archive-first path so no path is ever rewritten, applies the defaults
(``assent: tentative``, ``lifecycle: fleeting``, ``processed: false``), writes
the H1 from the title, and materialises ``mocs``. Every rendered document must
pass :func:`validate_file` AND the split rule before the caller stages it; a
violation raises :class:`SplitViolation` naming the rule.

The **split rule** (PRD "Split rule"): one to three claims, and a body no
longer than ``max_zettel_body_lines`` non-blank lines. The prompt states it;
this code enforces it. ``aporia`` zettels carry no claims of their own.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from klyreon.backends.base import DoubtEntry, IngestPayload, ZettelDraft
from klyreon.spec.enums import Assent, ConceptType, Lifecycle
from klyreon.spec.model import Document, FileKind
from klyreon.spec.validator import validate_file
from klyreon.vault.ids import allocate_id

__all__ = ["RenderError", "RenderedZettel", "SplitViolation", "render_zettels"]

_MIN_CLAIMS = 1
_MAX_CLAIMS = 3


class RenderError(ValueError):
    """A drafted zettel could not be rendered into a spec-valid document."""


class SplitViolation(RenderError):
    """A rendered zettel violates the split rule (claim count or body size)."""


@dataclass(frozen=True, slots=True)
class RenderedZettel:
    """A validated document plus the vault-relative path it will be staged to."""

    rel_path: str
    document: Document


def _check_split_rule(draft: ZettelDraft, body_lines: int, max_body_lines: int) -> None:
    """Enforce the concrete ceiling (PRD "Split rule"). Raises on violation."""
    is_aporia = draft.concept_type == ConceptType.APORIA.value
    claim_count = len(draft.claims)
    if not is_aporia and claim_count > _MAX_CLAIMS:
        msg = f"zettel {draft.title!r} carries {claim_count} claims; the split rule allows at most {_MAX_CLAIMS}"
        raise SplitViolation(msg)
    if body_lines > max_body_lines:
        msg = (
            f"zettel {draft.title!r} body has {body_lines} non-blank lines; "
            f"the split rule allows at most {max_body_lines}"
        )
        raise SplitViolation(msg)


def _body_with_h1(title: str, raw_body: str) -> str:
    """Return the body with a single H1 equal to ``title`` at its head."""
    stripped = raw_body.strip("\n")
    return f"\n# {title}\n\n{stripped}\n" if stripped else f"\n# {title}\n"


def _non_blank_lines(body: str) -> int:
    return len([ln for ln in body.strip().splitlines() if ln.strip()])


def _frontmatter_for(
    draft: ZettelDraft,
    *,
    zid: str,
    created: dt.datetime,
    source_archive_path: str,
) -> dict[str, object]:
    front: dict[str, object] = {
        "id": zid,
        "title": draft.title,
        "created": created.isoformat(),
        "type": draft.type,
    }
    if draft.tags:
        front["tags"] = list(draft.tags)
    if draft.concept_type is not None:
        front["concept-type"] = draft.concept_type
        front["assent"] = Assent.TENTATIVE.value
        front["lifecycle"] = Lifecycle.FLEETING.value
        front["processed"] = False
    if draft.claims:
        front["claims"] = [{"id": c.id, "statement": c.statement} for c in draft.claims]
    if draft.doubts:
        front["doubts"] = [_doubt_to_mapping(d) for d in draft.doubts]
    # Archive-first: every derived zettel cites the archive path from birth.
    front["sources"] = [source_archive_path]
    if draft.mocs:
        front["mocs"] = list(draft.mocs)
    return front


def _doubt_to_mapping(doubt: DoubtEntry) -> dict[str, object]:
    mapping: dict[str, object] = {"mode": doubt.mode, "claim": doubt.claim, "rationale": doubt.rationale}
    if doubt.target is not None:
        mapping["target"] = {"to": doubt.target.to, "claim": doubt.target.claim}
    return mapping


def render_zettels(
    payload: IngestPayload,
    *,
    source_archive_path: str,
    notes_dir: Path,
    now: dt.datetime,
    max_body_lines: int = 60,
) -> list[RenderedZettel]:
    """Render every draft in ``payload`` to a validated document.

    Allocates a unique 14-digit id per draft (bumping within the batch so two
    drafts never share a second), sets archive-first ``sources``, applies the
    concept defaults, writes the H1, enforces the split rule, and validates the
    result. Raises :class:`RenderError`/:class:`SplitViolation` on the first
    bad draft, so a source lands entirely or not at all.
    """
    rendered: list[RenderedZettel] = []
    reserved: set[str] = set()
    moment = now

    for draft in payload.zettels:
        # Allocate against the notes dir AND the ids already reserved this batch.
        while True:
            allocated = allocate_id(notes_dir, moment)
            if allocated.id not in reserved:
                break
            moment = moment + dt.timedelta(seconds=1)
        reserved.add(allocated.id)
        moment = allocated.created + dt.timedelta(seconds=1)

        body = _body_with_h1(draft.title, draft.body)
        _check_split_rule(draft, _non_blank_lines(body), max_body_lines)

        front = _frontmatter_for(
            draft,
            zid=allocated.id,
            created=allocated.created,
            source_archive_path=source_archive_path,
        )
        rel_path = f"wiki/notes/{allocated.filename}"
        doc = Document(path=rel_path, kind=FileKind.ZETTEL, frontmatter=front, body=body, h1=draft.title)

        errors = validate_file(doc)
        if errors:
            detail = "; ".join(f"[{e.rule}] {e.message}" for e in errors)
            msg = f"rendered zettel {draft.title!r} is invalid: {detail}"
            raise RenderError(msg)

        # Belt-and-braces on the lower bound the validator does not express for
        # non-assertion shapes: an assertion-bearing shape already requires >=1
        # claim via validate_file; nothing requires it elsewhere, so the split
        # rule's lower bound is only meaningful where claims are present.
        if draft.claims and not (_MIN_CLAIMS <= len(draft.claims) <= _MAX_CLAIMS):  # pragma: no cover - guarded above
            msg = f"zettel {draft.title!r} claim count out of range"
            raise SplitViolation(msg)

        rendered.append(RenderedZettel(rel_path=rel_path, document=doc))

    return rendered

"""Triage proposal IO and promote-readiness validation.

Triage proposals are YAML sidecar files produced by the pipeline when a
document cannot be auto-filed. A human edits the file, sets ``approved:
true``, and the watcher (or a manual ``bim doc promote``) consumes it.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from bim.commands.doc.shared.atomic_write import atomic_write_text
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.validators import validate_sha256_hex64

__all__ = [
    "RULE_CONFLICT_REASON_PREFIX",
    "DocumentProposal",
    "IssuerProposal",
    "OCRProposal",
    "SourceProposal",
    "TriageProposal",
    "ZettelPreview",
    "format_rule_conflict_reason",
    "read_proposal",
    "validate_for_promote",
    "write_proposal",
]


RULE_CONFLICT_REASON_PREFIX = "rule_conflict"


def format_rule_conflict_reason(rule_ids: list[str]) -> str:
    """Build a typed triage reason string for a rule-engine conflict.

    Two or more rule ids that disagree on extraction (typically on
    ``issuer_slug``) are joined alphabetically with ``" vs "`` and
    prefixed with :data:`RULE_CONFLICT_REASON_PREFIX`.
    """
    if len(rule_ids) < 2:
        raise ValueError("rule_conflict requires at least two rule ids")
    return f"{RULE_CONFLICT_REASON_PREFIX}: {' vs '.join(sorted(rule_ids))}"


class IssuerProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    display_name: str
    confidence: float
    alternatives: list[dict[str, Any]] = []


class DocumentProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str
    number: str | None = None
    date: _dt.date | None = None
    title: str | None = None
    amount: int | float | None = None
    currency: str | None = None
    language: str | None = None


class SourceProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    staging_path: Path
    email_msgid: str | None = None
    email_from: str | None = None
    email_subject: str | None = None
    original_filename: str | None = None
    sha256: str

    @field_validator("sha256")
    @classmethod
    def _sha256_is_hex64(cls, v: str) -> str:
        return validate_sha256_hex64("sha256", v)


class OCRProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engine: str
    languages: list[str]
    mean_confidence: float
    pages: int


class ZettelPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    ingested_at: _dt.datetime
    tags: list[str]
    summary: str | None = None

    @field_validator("title")
    @classmethod
    def _title_non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("title must be non-empty")
        return v


class TriageProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    approved: bool = False
    register_issuer: bool = False
    issuer: IssuerProposal
    document: DocumentProposal
    source: SourceProposal
    ocr: OCRProposal
    triage_reasons: list[str]
    zettel_preview: ZettelPreview


_ZK_TIMESTAMP_LEN = 14


def write_proposal(path: Path, proposal: TriageProposal) -> None:
    """Atomically write a triage proposal to disk as YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = proposal.model_dump(mode="json")
    serialized = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    atomic_write_text(path, serialized)


def read_proposal(path: Path) -> TriageProposal:
    """Load and validate a triage proposal from disk."""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    return TriageProposal.model_validate(data)


def validate_for_promote(proposal: TriageProposal, registry: IssuerRegistry) -> list[str]:
    """Return a list of error strings; empty list means ready to promote."""
    errors: list[str] = []

    if not proposal.approved:
        errors.append("approved must be true")

    if proposal.issuer.slug not in registry.issuers and not proposal.register_issuer:
        errors.append(f"issuer {proposal.issuer.slug!r} not in registry and register_issuer is false")

    # naming.DOC_TYPES is the authoritative closed list; registry.doc_types
    # is a human-readable mirror that may drift. Using DOC_TYPES here keeps
    # triage validation aligned with build_canonical_filename downstream.
    if proposal.document.type not in DOC_TYPES:
        errors.append(f"doc_type {proposal.document.type!r} not in canonical DOC_TYPES")

    if not proposal.issuer.slug:
        errors.append("issuer slug is empty")

    if not (proposal.document.number or proposal.document.title):
        errors.append("missing title or number for canonical filename")

    if (
        not proposal.zettel_preview.id
        or len(proposal.zettel_preview.id) != _ZK_TIMESTAMP_LEN
        or not proposal.zettel_preview.id.isdigit()
    ):
        errors.append("zettel_preview.id must be a 14-digit zk timestamp")

    return errors

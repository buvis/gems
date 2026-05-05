"""Triage proposal IO and promote-readiness validation.

Triage proposals are YAML sidecar files produced by the pipeline when a
document cannot be auto-filed. A human edits the file, sets ``approved:
true``, and the watcher (or a manual ``bim doc promote``) consumes it.
"""

from __future__ import annotations

import datetime as _dt
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.naming import DOC_TYPES

__all__ = [
    "DocumentProposal",
    "IssuerProposal",
    "OCRProposal",
    "SourceProposal",
    "TriageProposal",
    "ZettelPreview",
    "read_proposal",
    "validate_for_promote",
    "write_proposal",
]


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


class OCRProposal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engine: str
    languages: list[str]
    mean_confidence: float
    pages: int


class ZettelPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    ingest_date: _dt.date
    tags: list[str]


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
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


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

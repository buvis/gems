"""CommandPromote — file an approved triage proposal.

Reads ``<basename>.pdf.proposed.yml``, validates it, optionally registers a
new issuer, re-derives OCR from the staged PDF (does not trust user-edited
proposal values), then writes the zettel and atomically moves the PDF into
``<business_root>/<issuer-slug>/``.

On any failure during the file-move + record stages, the command returns a
``CommandResult(success=False, ...)`` without rollback - the spec accepts a
mid-flight crash leaving partial state in exchange for a simpler design.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast, get_args

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.issuers import load_registry, register_issuer
from bim.commands.doc.shared.naming import build_canonical_filename, slugify
from bim.commands.doc.shared.state_db import ProcessedRow
from bim.commands.doc.shared.triage import read_proposal, validate_for_promote
from bim.commands.doc.shared.zettel_helpers import build_zettel_tags, to_tilde_path
from bim.commands.doc.shared.zettel_writer import (
    DocumentZettelFrontmatter,
    IngestSource,
    build_zettel_body,
)

if TYPE_CHECKING:
    from bim.commands.doc.shared.issuers import IssuerRegistry
    from bim.commands.doc.shared.ocr import OCRResult, OCRRunner
    from bim.commands.doc.shared.settings_models import DocSettings
    from bim.commands.doc.shared.state_db import StateDB
    from bim.commands.doc.shared.triage import TriageProposal
    from bim.commands.doc.shared.zettel_writer import ZettelWriter
    from bim.params.doc_promote import PromoteParams

__all__ = ["CommandPromote", "PromoteServices"]

# Runtime-resolved tuple of valid ingest_source literals so we can validate
# strings coming from YAML and narrow them safely for the Pydantic model.
_VALID_INGEST_SOURCES: tuple[str, ...] = get_args(IngestSource)


@dataclass(frozen=True)
class PromoteServices:
    """Bundle of the boundary adapters CommandPromote depends on."""

    registry: IssuerRegistry
    registry_path: Path
    lock_path: Path
    state_db: StateDB
    ocr_runner: OCRRunner
    zettel_writer: ZettelWriter


@dataclass(frozen=True)
class _PromoteContext:
    """Resolved inputs that flow through the promote stages."""

    proposal: TriageProposal
    proposal_path: Path
    sibling_pdf: Path
    registry: IssuerRegistry


@dataclass(frozen=True)
class _NamePlan:
    """Canonical filename + derived paths produced by the naming stage."""

    canonical_filename: str
    target_pdf: Path
    zk_timestamp: str


class CommandPromote:
    """Promote a human-approved triage proposal into a filed document."""

    def __init__(self, *, params: PromoteParams, settings: DocSettings, services: PromoteServices) -> None:
        self._params = params
        self._settings = settings
        self._services = services

    def execute(self) -> CommandResult:
        loaded = self._load_and_validate()
        if isinstance(loaded, CommandResult):
            return loaded

        registry_after_register = self._maybe_register_issuer(loaded.proposal)
        if isinstance(registry_after_register, CommandResult):
            return registry_after_register
        ctx = (
            loaded
            if registry_after_register is None
            else _PromoteContext(
                proposal=loaded.proposal,
                proposal_path=loaded.proposal_path,
                sibling_pdf=loaded.sibling_pdf,
                registry=registry_after_register,
            )
        )

        ocr_or_err = self._run_ocr(ctx.sibling_pdf)
        if isinstance(ocr_or_err, CommandResult):
            return ocr_or_err

        plan_or_err = self._build_name_plan(ctx.proposal)
        if isinstance(plan_or_err, CommandResult):
            return plan_or_err

        return self._finalize(ctx, ocr_or_err, plan_or_err)

    # --------- stage 1: load + validate ---------

    def _load_and_validate(self) -> _PromoteContext | CommandResult:
        proposal_path = self._params.proposed_yml_path
        if not proposal_path.exists():
            return CommandResult(success=False, error=f"proposal not found: {proposal_path}")

        sibling_pdf = self._derive_sibling_pdf(proposal_path)
        if not sibling_pdf.exists():
            return CommandResult(success=False, error=f"sibling pdf not found: {sibling_pdf}")

        try:
            proposal = read_proposal(proposal_path)
        except Exception as exc:
            return CommandResult(success=False, error=f"could not read proposal: {exc}")

        errors = validate_for_promote(proposal, self._services.registry)
        if errors:
            return CommandResult(success=False, error="; ".join(errors))

        if proposal.source.kind not in _VALID_INGEST_SOURCES:
            return CommandResult(
                success=False,
                error=f"unsupported source kind {proposal.source.kind!r}; expected one of {_VALID_INGEST_SOURCES}",
            )

        return _PromoteContext(
            proposal=proposal,
            proposal_path=proposal_path,
            sibling_pdf=sibling_pdf,
            registry=self._services.registry,
        )

    # --------- stage 2: register new issuer if requested ---------

    def _maybe_register_issuer(self, proposal: TriageProposal) -> IssuerRegistry | CommandResult | None:
        """Return the post-register registry, or None if no register requested.

        Also creates ``<business_root>/<slug>/inbox/`` per spec §3 - every
        registered issuer is expected to have an inbox/ subfolder for manual
        document filing.
        """
        if not proposal.register_issuer:
            return None
        try:
            register_issuer(
                self._services.registry_path,
                self._services.lock_path,
                slug=proposal.issuer.slug,
                display_name=proposal.issuer.display_name,
                aliases=[],
            )
        except ValueError as exc:
            return CommandResult(success=False, error=f"register_issuer failed: {exc}")
        inbox_dir = self._settings.paths.business_root / proposal.issuer.slug / "inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        return load_registry(self._services.registry_path)

    # --------- stage 3: re-derive OCR ---------

    def _run_ocr(self, sibling_pdf: Path) -> OCRResult | CommandResult:
        try:
            return self._services.ocr_runner.run(sibling_pdf)
        except Exception as exc:
            return CommandResult(success=False, error=f"OCR failed during promote: {exc}")

    # --------- stage 4: build canonical name + target path ---------

    def _build_name_plan(self, proposal: TriageProposal) -> _NamePlan | CommandResult:
        title_or_number = proposal.document.number or proposal.document.title or ""
        if not title_or_number:
            return CommandResult(success=False, error="proposal missing title/number for canonical filename")
        try:
            title_slug = slugify(title_or_number)
        except ValueError as exc:
            return CommandResult(success=False, error=f"slugify failed: {exc}")

        zk_timestamp = self._zk_timestamp(proposal.document.date or proposal.zettel_preview.ingest_date)

        try:
            canonical_filename = build_canonical_filename(
                zk_timestamp=zk_timestamp,
                issuer_slug=proposal.issuer.slug,
                title_or_number=title_slug,
                doc_type=proposal.document.type,
            )
        except ValueError as exc:
            return CommandResult(success=False, error=f"canonical filename failed: {exc}")

        target_pdf = self._settings.paths.business_root / proposal.issuer.slug / canonical_filename
        target_pdf.parent.mkdir(parents=True, exist_ok=True)
        return _NamePlan(
            canonical_filename=canonical_filename,
            target_pdf=target_pdf,
            zk_timestamp=zk_timestamp,
        )

    # --------- stage 5: write zettel, move pdf, record processed, delete proposal ---------

    def _finalize(self, ctx: _PromoteContext, ocr_result: OCRResult, plan: _NamePlan) -> CommandResult:
        # Use the OCR'd PDF (which carries the freshly-derived text layer) as
        # the source of truth for both the recorded sha and the file we move.
        # When OCR ran in skip/redo mode in place, ocr_result.pdf_path equals
        # ctx.sibling_pdf and this is a no-op. When the full-OCR branch fired,
        # ocr_result.pdf_path is a new temp file with the embedded text layer
        # and we file that instead, otherwise the zettel body would describe
        # OCR text that the filed PDF does not contain.
        source_pdf = ocr_result.pdf_path
        sha = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
        ingest_today = date.today()

        frontmatter_or_err = self._build_frontmatter(ctx, ocr_result, plan, sha, ingest_today)
        if isinstance(frontmatter_or_err, CommandResult):
            return frontmatter_or_err
        frontmatter = frontmatter_or_err

        body = build_zettel_body(frontmatter, ocr_result.ocr_text, self._settings.zettel)
        try:
            zettel_path = self._services.zettel_writer.write(frontmatter, body)
        except Exception as exc:
            return CommandResult(success=False, error=f"zettel write failed: {exc}")

        try:
            source_pdf.replace(plan.target_pdf)
        except OSError as exc:
            return CommandResult(success=False, error=f"pdf move failed: {exc}")
        # If full-OCR produced a new path, the original triage PDF is now
        # orphaned. Clean it up so _triage/ doesn't accumulate stale copies.
        if source_pdf != ctx.sibling_pdf:
            try:
                ctx.sibling_pdf.unlink()
            except OSError:
                # Non-fatal: orphaned triage PDF is a small leak, not data loss.
                pass

        try:
            self._services.state_db.record_processed(
                ProcessedRow(
                    sha256=sha,
                    canonical_filename=plan.canonical_filename,
                    issuer_slug=ctx.proposal.issuer.slug,
                    doc_type=ctx.proposal.document.type,
                    processed_at=datetime.now(timezone.utc),
                    extraction_method="manual",
                )
            )
        except Exception as exc:
            return CommandResult(success=False, error=f"state_db record failed: {exc}")

        try:
            ctx.proposal_path.unlink()
        except OSError as exc:
            return CommandResult(success=False, error=f"could not delete proposal: {exc}")

        return CommandResult(
            success=True,
            metadata={
                "zettel_path": str(zettel_path),
                "pdf_path": str(plan.target_pdf),
                "canonical_filename": plan.canonical_filename,
                "sha256": sha,
            },
        )

    def _build_frontmatter(
        self,
        ctx: _PromoteContext,
        ocr_result: OCRResult,
        plan: _NamePlan,
        sha: str,
        ingest_today: date,
    ) -> DocumentZettelFrontmatter | CommandResult:
        try:
            return DocumentZettelFrontmatter(
                id=plan.zk_timestamp,
                doc_type=ctx.proposal.document.type,
                issuer_slug=ctx.proposal.issuer.slug,
                issuer_display=(
                    ctx.proposal.issuer.display_name or ctx.registry.issuers[ctx.proposal.issuer.slug].display_name
                ),
                doc_number=ctx.proposal.document.number,
                doc_date=ctx.proposal.document.date or ingest_today,
                doc_amount=ctx.proposal.document.amount,
                doc_currency=ctx.proposal.document.currency,
                doc_language=ctx.proposal.document.language,
                ingest_date=ingest_today,
                ingest_source=cast(IngestSource, ctx.proposal.source.kind),
                file_path=to_tilde_path(plan.target_pdf),
                file_sha256=sha,
                ocr_engine=self._settings.ocr.engine,
                ocr_mean_confidence=ocr_result.mean_confidence,
                extraction_method="manual",
                tags=build_zettel_tags(
                    ctx.proposal.document.type, ctx.proposal.issuer.slug, ctx.proposal.document.date
                ),
            )
        except Exception as exc:
            return CommandResult(success=False, error=f"frontmatter validation failed: {exc}")

    # --------- helpers ---------

    @staticmethod
    def _derive_sibling_pdf(proposal_path: Path) -> Path:
        """``foo.pdf.proposed.yml`` -> ``foo.pdf``."""
        name = proposal_path.name
        if name.endswith(".proposed.yml"):
            return proposal_path.with_name(name[: -len(".proposed.yml")])
        return proposal_path.with_suffix(".pdf")

    @staticmethod
    def _zk_timestamp(when: date) -> str:
        return when.strftime("%Y%m%d") + "000000"

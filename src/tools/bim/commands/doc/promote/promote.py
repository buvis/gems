"""CommandPromote — file an approved triage proposal.

Reads ``<basename>.pdf.proposed.yml``, validates it, optionally registers a
new issuer, re-derives OCR from the staged PDF (does not trust user-edited
proposal values), then writes the zettel and atomically moves the PDF into
``<business_root>/<issuer-slug>/``.

On any failure during the file-move + record stages, the command returns a
``CommandResult(success=False, ...)`` without rollback - the spec accepts a
mid-flight crash leaving partial state in exchange for a simpler design.

**Same-volume invariant.** When the OCR runner's full-OCR branch fires at
promote time it returns a temp-file ``pdf_path``; ``_finalize`` moves that
into ``<business_root>/<issuer-slug>/`` via ``Path.replace``. The move is
atomic only when the system tempdir and the business root share a
filesystem. The pipeline already documents this for ingest; the same
invariant applies to promote when full OCR fires.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, get_args

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.hashing import sha256_file
from bim.commands.doc.shared.issuers import register_issuer
from bim.commands.doc.shared.naming import resolve_collision, slugify
from bim.commands.doc.shared.pipeline_helpers import PromoteFrontmatterContext, build_promote_frontmatter
from bim.commands.doc.shared.state_db import ProcessedRow
from bim.commands.doc.shared.triage import read_proposal, validate_for_promote
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
            new_registry = register_issuer(
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
        return new_registry

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

        # zk_timestamp picks the document's own date when known, otherwise
        # the proposal preview's ingestion timestamp (now a ``datetime``;
        # take its date component to keep the existing ``YYYYMMDD000000``
        # encoding from ``_zk_timestamp``).
        zk_timestamp = self._zk_timestamp(proposal.document.date or proposal.zettel_preview.ingested_at.date())

        # Check-then-write gap against _finalize's later write: inherited
        # from the ingest path this resolver came from, accepted, not introduced.
        try:
            canonical_filename, resolved_zk_timestamp, target_pdf = resolve_collision(
                zk_timestamp=zk_timestamp,
                issuer_slug=proposal.issuer.slug,
                title_or_number=title_slug,
                doc_type=proposal.document.type,
                business_root=self._settings.paths.business_root,
                vault_dir=self._settings.paths.vault_root / self._settings.paths.vault_documents_subdir,
            )
        except ValueError as exc:
            return CommandResult(success=False, error=f"could not build a canonical filename: {exc}")
        except OSError as exc:
            return CommandResult(success=False, error=f"filesystem error while resolving the filename collision: {exc}")

        return _NamePlan(
            canonical_filename=canonical_filename,
            target_pdf=target_pdf,
            zk_timestamp=resolved_zk_timestamp,
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
        sha = sha256_file(source_pdf)

        frontmatter_or_err = self._build_frontmatter(ctx, ocr_result, plan, sha)
        if isinstance(frontmatter_or_err, CommandResult):
            return frontmatter_or_err
        frontmatter = frontmatter_or_err

        body = build_zettel_body(
            frontmatter,
            ocr_result.ocr_text,
            summary=ctx.proposal.zettel_preview.summary,
            settings=self._settings.zettel,
        )
        try:
            zettel_path = self._services.zettel_writer.write(frontmatter, body, issuer_slug=ctx.proposal.issuer.slug)
        except Exception as exc:
            return CommandResult(success=False, error=f"zettel write failed: {exc}")

        try:
            source_pdf.replace(plan.target_pdf)
        except OSError as exc:
            return CommandResult(success=False, error=f"pdf move failed: {exc}")
        # If full-OCR produced a new path, the original triage PDF is now
        # orphaned. Clean it up so _triage/ doesn't accumulate stale copies.
        # Use missing_ok so this never fails when the original was already
        # removed by a concurrent promote (rare but possible).
        if source_pdf != ctx.sibling_pdf:
            ctx.sibling_pdf.unlink(missing_ok=True)

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
            # Refresh rule freshness when this triage came from a rule-engine
            # match (``applied_rule_id`` set by the pipeline). Pre-existing
            # proposals without the field skip the refresh and behave as before.
            if ctx.proposal.applied_rule_id is not None:
                self._services.state_db.record_rule_match(
                    ctx.proposal.applied_rule_id,
                    datetime.now(timezone.utc),
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
    ) -> DocumentZettelFrontmatter | CommandResult:
        # Resolve issuer display (proposal first, registry fallback) then defer
        # the actual frontmatter assembly to the shared helper. The helper is
        # the same one used by the cross-path consistency test, which pins
        # PRD criterion 8.
        issuer_display = ctx.proposal.issuer.display_name or ctx.registry.issuers[ctx.proposal.issuer.slug].display_name
        return build_promote_frontmatter(
            PromoteFrontmatterContext(
                proposal=ctx.proposal,
                issuer_display=issuer_display,
                issuer_slug=ctx.proposal.issuer.slug,
                zk_timestamp=plan.zk_timestamp,
                target_pdf=plan.target_pdf,
                sha=sha,
                ocr_engine=self._settings.ocr.engine,
                ocr_mean_confidence=ocr_result.mean_confidence,
            )
        )

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

"""8-step pipeline orchestrator for the bim doc subsystem.

Runs the canonical pipeline from `dev/local/specs/bim-doc-architecture.md`
section 6: dedup -> OCR -> classify -> extract -> name -> write zettel ->
file PDF (or triage). Boundary services (OCR, classifier, extractor) are
injected via the constructor and mocked at the class boundary in tests.

**Same-volume invariant.** The final ``os.replace`` step (Step 8) is atomic
only when the staging directory and the business root share a filesystem.
The spec mandates locating ``state_dir/inbox/`` outside iCloud (which
synchronises asynchronously) so the move into the iCloud-backed business
root is the only iCloud touchpoint and remains atomic. Crossing volumes
silently breaks this invariant.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.filesystem import atomic_write_text
from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.extractor import IncompleteExtraction
from bim.commands.doc.shared.hashing import sha256_file
from bim.commands.doc.shared.naming import build_canonical_filename, resolve_collision, slugify
from bim.commands.doc.shared.pipeline_helpers import (
    ClassifyStage,
    ExtractStage,
    FilingContext,
    PipelineStages,
    RuleStage,
    TriageContext,
    applied_rule_id as _applied_rule_id,
    build_filing_context_from_stages,
    build_filing_frontmatter,
    build_filing_result,
    build_triage_context,
    compose_triage_title as _compose_triage_title,
    retry_llm_call as _retry_llm_call,
    rule_extraction_method as _rule_extraction_method,
)
from bim.commands.doc.shared.progress import NoOpProgressReporter
from bim.commands.doc.shared.rules.engine import RuleEngine
from bim.commands.doc.shared.rules.models import RuleResult, SourceMetadata
from bim.commands.doc.shared.state_db import ProcessedRow
from bim.commands.doc.shared.triage import (
    DocumentProposal,
    IssuerProposal,
    OCRProposal,
    SourceProposal,
    TriageProposal,
    ZettelPreview,
    format_rule_conflict_reason,
    write_proposal,
)
from bim.commands.doc.shared.zettel_helpers import build_zettel_tags
from bim.commands.doc.shared.zettel_writer import build_zettel_body

if TYPE_CHECKING:
    from bim.commands.doc.shared.classifier import Classifier, ClassifyResult
    from bim.commands.doc.shared.extractor import Extractor, ExtractResult
    from bim.commands.doc.shared.issuers import IssuerRegistry
    from bim.commands.doc.shared.ocr import OCRResult, OCRRunner
    from bim.commands.doc.shared.progress import ProgressReporter
    from bim.commands.doc.shared.settings_models import DocSettings
    from bim.commands.doc.shared.state_db import StateDB
    from bim.commands.doc.shared.zettel_writer import ZettelWriter
    from bim.params.doc_ingest import IngestParams

__all__ = ["IngestOutcome", "Pipeline", "PipelineServices"]

# Sentinel `extraction_method` for a `processed` row stamped while the
# document still waits in `_triage/` for human review, not yet filed.
_PENDING_TRIAGE_EXTRACTION_METHOD = "pending-triage"


class IngestOutcome(str, Enum):
    """Three terminal pipeline outcomes recorded in ``CommandResult.metadata``."""

    FILED = "filed"
    TRIAGED = "triaged"
    DUPLICATE = "duplicate"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PipelineServices:
    """Bundle of the boundary adapters the pipeline depends on.

    Grouping them keeps the ``Pipeline`` constructor narrow and makes it
    obvious that mocking these services is the supported test seam.
    """

    state_db: StateDB
    ocr_runner: OCRRunner
    classifier: Classifier
    extractor: Extractor
    registry: IssuerRegistry
    zettel_writer: ZettelWriter


class Pipeline:
    """Coordinates the eight pipeline steps for a single ingest invocation.

    Boundary services are injected via :class:`PipelineServices` so tests
    can mock them at the class boundary (subprocess/HTTP calls live behind
    these adapters and are not re-mocked here).
    """

    def __init__(self, settings: DocSettings, services: PipelineServices) -> None:
        self._settings = settings
        self._services = services

    # Forwarding properties so internal call sites read like the bundled
    # services were direct attributes - keeps the rest of the module clean
    # without leaking the "services" container name everywhere.
    @property
    def _state_db(self) -> StateDB:
        return self._services.state_db

    @property
    def _ocr_runner(self) -> OCRRunner:
        return self._services.ocr_runner

    @property
    def _classifier(self) -> Classifier:
        return self._services.classifier

    @property
    def _extractor(self) -> Extractor:
        return self._services.extractor

    @property
    def _registry(self) -> IssuerRegistry:
        return self._services.registry

    @property
    def _zettel_writer(self) -> ZettelWriter:
        return self._services.zettel_writer

    # --------- public entrypoint ---------

    def run(self, params: IngestParams, *, reporter: ProgressReporter | None = None) -> CommandResult:
        """Run the 8-step pipeline against a single staged document.

        The optional ``reporter`` is notified before each slow boundary call
        (OCR, classifier, extractor). Defaults to a no-op so batch callers
        and tests can ignore it. The reporter is the caller's responsibility
        to enter/exit; ``run`` only calls ``.stage()``.
        """
        active_reporter: ProgressReporter = reporter if reporter is not None else NoOpProgressReporter()
        sha = sha256_file(params.staging_path)

        # Step 1: dedup (read-only fast path)
        dedup = self._state_db.dedup(sha)
        if dedup.is_duplicate and dedup.existing_row is not None:
            self._write_duplicate_sidecar(params.staging_path, dedup.existing_row)
            return CommandResult(
                success=True,
                metadata={
                    "outcome": IngestOutcome.DUPLICATE.value,
                    "existing_canonical_filename": dedup.existing_row.canonical_filename,
                    "sha256": sha,
                },
            )

        # Step 1b: claim (atomic check-and-reserve). A claim older than
        # ``claim_max_age_minutes`` belonged to a worker that died without
        # releasing it, so it is taken over rather than trusted.
        if not self._state_db.claim(sha, max_age=timedelta(minutes=self._settings.claim_max_age_minutes)):
            # Another worker already claimed; treat as duplicate from this caller's POV.
            return CommandResult(
                success=True,
                metadata={"outcome": IngestOutcome.DUPLICATE.value, "sha256": sha},
            )

        try:
            return self._run_after_claim(params, sha, active_reporter)
        except Exception as exc:
            # Map any escaping exception to a structured CommandResult per AGENTS.md
            # "never let raw exceptions reach the user" - the CLI handler turns
            # success=False into console.failure rather than a stack trace.
            # Capture exception_type/repr alongside stage so log analysis can
            # distinguish failure modes without violating the no-stack-trace rule.
            return CommandResult(
                success=False,
                error=f"pipeline failed: {exc}",
                metadata={
                    "sha256": sha,
                    "stage": "post-claim",
                    "exception_type": type(exc).__name__,
                    "exception_repr": repr(exc),
                },
            )
        finally:
            # Single release point for every exit - return, exception, and
            # BaseException alike (a Ctrl-C must not park the sha forever).
            # On the filed path the processed row already prevents re-ingestion;
            # the claim row was only the in-flight reservation.
            self._state_db.release_claim(sha)

    # --------- internals ---------

    def _run_after_claim(self, params: IngestParams, sha: str, reporter: ProgressReporter) -> CommandResult:
        rule_stage = self._run_ocr_and_rules(params, sha, reporter)
        if isinstance(rule_stage, CommandResult):
            return rule_stage

        applied_rule_id = _applied_rule_id(rule_stage.rule_result)
        classify_stage = self._classify_after_rules(params, rule_stage, reporter)
        stages = PipelineStages(params=params, sha=sha, rule_stage=rule_stage, classify_stage=classify_stage)

        classify_result = classify_stage.classify_result
        if classify_result is None:
            return self._triage(
                build_triage_context(
                    stages,
                    classify_result=None,
                    extract_result=None,
                    reasons=classify_stage.triage_reasons,
                    applied_rule_id=applied_rule_id,
                )
            )

        extract_stage = self._extract_after_classify(params, rule_stage, classify_result, reporter)
        triage_reasons = classify_stage.triage_reasons + extract_stage.triage_reasons
        if triage_reasons or extract_stage.extract_result is None:
            return self._triage(
                build_triage_context(
                    stages,
                    classify_result=classify_result,
                    extract_result=extract_stage.extract_result,
                    reasons=triage_reasons,
                    applied_rule_id=applied_rule_id,
                )
            )
        return self._finalize_filing(
            build_filing_context_from_stages(stages, classify_result, extract_stage.extract_result)
        )

    def _run_ocr_and_rules(
        self, params: IngestParams, sha: str, reporter: ProgressReporter
    ) -> RuleStage | CommandResult:
        reporter.stage("running OCR")
        ocr_result = self._ocr_runner.run(params.staging_path)

        source_metadata = self._build_source_metadata(params)
        rule_result = self._run_rules(ocr_result.ocr_text, source_metadata, params)
        if rule_result.kind == "conflict":
            return self._triage(
                TriageContext(
                    params=params,
                    sha=sha,
                    ocr_result=ocr_result,
                    classify_result=None,
                    extract_result=None,
                    reasons=[format_rule_conflict_reason(rule_result.conflicting_rules)],
                    issuer_slug="",
                    issuer_display="",
                )
            )

        extraction_method = f"llm:{self._settings.classifier.primary_model}"
        use_pinned = rule_result.kind in {"full", "partial"}
        if use_pinned:
            if rule_result.rule_id is not None:
                self._state_db.record_rule_match(
                    rule_result.rule_id,
                    datetime.now(timezone.utc),
                )
            extraction_method = _rule_extraction_method(rule_result)
        return RuleStage(ocr_result, rule_result, extraction_method, use_pinned)

    def _classify_after_rules(
        self, params: IngestParams, rule_stage: RuleStage, reporter: ProgressReporter
    ) -> ClassifyStage:
        reporter.stage("classifying document")
        if rule_stage.use_pinned:
            classify_result, classify_error = self._classify_with_pinned(
                params, rule_stage.ocr_result, rule_stage.rule_result.pinned
            )
        else:
            classify_result, classify_error = self._classify(params, rule_stage.ocr_result)

        issuer_slug, issuer_display = self._resolve_issuer(params, classify_result)
        triage_reasons = self._collect_classify_triage_reasons(
            classify_error=classify_error,
            classify_result=classify_result,
            issuer_slug=issuer_slug,
        )
        return ClassifyStage(classify_result, issuer_slug, issuer_display, triage_reasons)

    def _extract_after_classify(
        self,
        params: IngestParams,
        rule_stage: RuleStage,
        classify_result: ClassifyResult,
        reporter: ProgressReporter,
    ) -> ExtractStage:
        reporter.stage("extracting fields")
        hints = self._build_extractor_hints(params)

        def _extract_call(model: str) -> ExtractResult:
            if rule_stage.use_pinned:
                return self._extractor.extract_with_pinned(
                    rule_stage.ocr_result.ocr_text,
                    classify_result.doc_type,
                    rule_stage.rule_result.pinned,
                    model=model,
                    hints=hints,
                )
            return self._extractor.extract_with_model(
                rule_stage.ocr_result.ocr_text,
                classify_result.doc_type,
                model=model,
                hints=hints,
            )

        triage_reasons: list[str] = []
        extract_result: ExtractResult | None = None
        try:
            extract_result = _retry_llm_call(
                func=_extract_call,
                primary_model=self._settings.classifier.primary_model,
                fallback_model=self._settings.classifier.fallback_model,
                max_retries=self._settings.classifier.max_retries,
                is_transient=lambda exc: isinstance(exc, IncompleteExtraction) and exc.transient,
            )
        except IncompleteExtraction as exc:
            extract_result = exc.partial
            triage_reasons.extend(exc.reasons)
        except Exception as exc:
            triage_reasons.append(f"extractor error: {exc}")
        return ExtractStage(extract_result, triage_reasons)

    def _finalize_filing(self, ctx: FilingContext) -> CommandResult:
        slug_title = self._slug_title_or_triage(ctx)
        if isinstance(slug_title, CommandResult):
            return slug_title

        zk_timestamp = self._zk_timestamp(ctx.extract_result.date)
        canonical_filename, zk_timestamp, target_pdf = resolve_collision(
            zk_timestamp=zk_timestamp,
            issuer_slug=ctx.issuer_slug,
            title_or_number=slug_title,
            doc_type=ctx.classify_result.doc_type,
            business_root=self._settings.paths.business_root,
            vault_dir=self._settings.paths.vault_root / self._settings.paths.vault_documents_subdir,
        )
        return self._file_document(ctx, canonical_filename, zk_timestamp, target_pdf)

    def _slug_title_or_triage(self, ctx: FilingContext) -> str | CommandResult:
        title_or_number = ctx.extract_result.number or ctx.extract_result.title
        if not title_or_number:
            return self._triage(
                TriageContext(
                    params=ctx.params,
                    sha=ctx.sha,
                    ocr_result=ctx.ocr_result,
                    classify_result=ctx.classify_result,
                    extract_result=ctx.extract_result,
                    reasons=["missing title and number for canonical filename"],
                    issuer_slug=ctx.issuer_slug,
                    issuer_display=ctx.issuer_display,
                )
            )
        try:
            return slugify(title_or_number)
        except ValueError:
            return self._triage(
                TriageContext(
                    params=ctx.params,
                    sha=ctx.sha,
                    ocr_result=ctx.ocr_result,
                    classify_result=ctx.classify_result,
                    extract_result=ctx.extract_result,
                    reasons=["title_or_number slugifies to empty"],
                    issuer_slug=ctx.issuer_slug,
                    issuer_display=ctx.issuer_display,
                )
            )

    def _file_document(
        self, ctx: FilingContext, canonical_filename: str, zk_timestamp: str, target_pdf: Path
    ) -> CommandResult:
        ingested_at = datetime.now().astimezone()
        frontmatter = build_filing_frontmatter(
            ctx,
            zk_timestamp=zk_timestamp,
            target_pdf=target_pdf,
            ingested_at=ingested_at,
            ocr_engine=self._settings.ocr.engine,
        )
        body = build_zettel_body(
            frontmatter,
            ctx.ocr_result.ocr_text,
            summary=ctx.extract_result.summary,
            settings=self._settings.zettel,
        )
        zettel_path = self._zettel_writer.write(frontmatter, body, issuer_slug=ctx.issuer_slug)

        os.replace(ctx.ocr_result.pdf_path, target_pdf)

        self._state_db.record_processed(
            ProcessedRow(
                sha256=ctx.sha,
                canonical_filename=canonical_filename,
                issuer_slug=ctx.issuer_slug,
                doc_type=ctx.classify_result.doc_type,
                processed_at=datetime.now(timezone.utc),
                extraction_method=ctx.extraction_method,
            )
        )

        return build_filing_result(
            outcome=IngestOutcome.FILED.value,
            zettel_path=zettel_path,
            target_pdf=target_pdf,
            canonical_filename=canonical_filename,
            sha=ctx.sha,
        )

    def _collect_classify_triage_reasons(
        self,
        *,
        classify_error: str | None,
        classify_result: ClassifyResult | None,
        issuer_slug: str,
    ) -> list[str]:
        """Bundle the classify-stage triage-reason logic into one helper.

        Extracted from ``_run_after_claim`` to keep that orchestrator under
        the ruff PLR0912 branch limit. Behaviour byte-identical to the inline
        version it replaced: order is preserved (classify_error → issuer →
        confidence) so existing snapshot tests still match.
        """
        reasons: list[str] = []
        if classify_error is not None:
            reasons.append(classify_error)
        if not issuer_slug:
            guess = classify_result.issuer_guess if classify_result is not None else None
            if guess:
                reasons.append(f"unknown issuer (classifier guessed {guess!r}, not in registry)")
            else:
                reasons.append("unknown issuer (classifier returned no slug)")
        if classify_result is not None and classify_result.confidence < self._settings.classifier.triage_threshold:
            reasons.append(
                f"classifier confidence below threshold "
                f"({classify_result.confidence:.2f} < {self._settings.classifier.triage_threshold:.2f})"
            )
        return reasons

    def _classify(self, params: IngestParams, ocr_result: OCRResult) -> tuple[ClassifyResult | None, str | None]:
        """Run classifier with retry+fallback, returning ``(result, error_message)``.

        Spec §11 retry semantics: HTTP transport failures (``ClassifierError``)
        retry up to ``classifier.max_retries`` times against ``primary_model``,
        then fall back once to ``fallback_model``. ``requests.exceptions.Timeout``
        is treated as a non-transient (re-raised unwrapped by the boundary)
        and short-circuits to triage without retry/fallback.
        """
        from bim.commands.doc.shared.classifier import ClassifierError

        doc_type_only = params.source == "issuer-inbox"
        source_metadata = self._build_source_metadata(params)

        def _call(model: str) -> ClassifyResult:
            return self._classifier.classify_with_model(
                ocr_result.ocr_text,
                source_metadata,
                self._registry,
                model=model,
                doc_type_only=doc_type_only,
            )

        try:
            result = _retry_llm_call(
                func=_call,
                primary_model=self._settings.classifier.primary_model,
                fallback_model=self._settings.classifier.fallback_model,
                max_retries=self._settings.classifier.max_retries,
                is_transient=lambda exc: isinstance(exc, ClassifierError) and exc.transient,
            )
        except Exception as exc:
            return None, f"classifier error: {exc}"
        return result, None

    def _classify_with_pinned(
        self, params: IngestParams, ocr_result: OCRResult, pinned: dict[str, object]
    ) -> tuple[ClassifyResult | None, str | None]:
        """Run pinned classifier path with the same retry semantics as classification."""
        from bim.commands.doc.shared.classifier import ClassifierError

        source_metadata = self._build_source_metadata(params)

        def _call(model: str) -> ClassifyResult:
            return self._classifier.classify_with_pinned(
                ocr_result.ocr_text,
                source_metadata,
                self._registry,
                pinned,
                model=model,
            )

        try:
            result = _retry_llm_call(
                func=_call,
                primary_model=self._settings.classifier.primary_model,
                fallback_model=self._settings.classifier.fallback_model,
                max_retries=self._settings.classifier.max_retries,
                is_transient=lambda exc: isinstance(exc, ClassifierError) and exc.transient,
            )
        except Exception as exc:
            return None, f"classifier error: {exc}"
        return result, None

    def _resolve_issuer(self, params: IngestParams, classify_result: ClassifyResult | None) -> tuple[str, str]:
        """Pick the canonical issuer slug + display for this run.

        For issuer-inbox source, the slug is pinned by ``params.issuer_slug_hint``
        (validated against the registry). Otherwise, the classifier's
        already-canonicalised result is used. Returns ``("", "")`` when no slug
        could be resolved - the caller treats this as a triage condition.
        """
        if params.source == "issuer-inbox":
            hint = params.issuer_slug_hint
            if hint and hint in self._registry.issuers:
                entry = self._registry.issuers[hint]
                return hint, entry.display_name
            return "", ""

        if classify_result is not None and classify_result.issuer_slug:
            slug = classify_result.issuer_slug
            display = classify_result.issuer_display or slug
            return slug, display

        return "", ""

    def _triage(self, ctx: TriageContext) -> CommandResult:
        zk_timestamp = self._zk_timestamp(ctx.extract_result.date if ctx.extract_result is not None else None)
        title_or_number_raw = ""
        if ctx.extract_result is not None:
            title_or_number_raw = ctx.extract_result.number or ctx.extract_result.title or ""
        if not title_or_number_raw:
            title_or_number_raw = "unknown"
        try:
            title_slug = slugify(title_or_number_raw)
        except ValueError:
            title_slug = "unknown"

        # Fall back to the classifier's slugified guess (when present) so the
        # triage filename, proposal, and zettel preview surface something the
        # human can react to instead of the literal string "unknown".
        # Registration still requires the user to flip register_issuer=true.
        guess_slug = ctx.classify_result.issuer_guess if ctx.classify_result is not None else None
        slug_for_filename = ctx.issuer_slug or guess_slug or "unknown"
        proposal_slug = ctx.issuer_slug or guess_slug or ""
        doc_type_for_filename = ctx.classify_result.doc_type if ctx.classify_result is not None else "other"
        try:
            basename = build_canonical_filename(
                zk_timestamp=zk_timestamp,
                issuer_slug=slug_for_filename,
                title_or_number=title_slug,
                doc_type=doc_type_for_filename,
            )
        except ValueError:
            # Last-resort fallback if any inputs slip past validation upstream.
            basename = f"{zk_timestamp}-unknown-unknown.{doc_type_for_filename}.pdf"

        triage_dir = self._settings.paths.business_root / "_triage"
        triage_dir.mkdir(parents=True, exist_ok=True)
        triage_pdf = triage_dir / basename
        proposal_path = triage_dir / (basename + ".proposed.yml")

        os.replace(ctx.ocr_result.pdf_path, triage_pdf)

        proposal = TriageProposal(
            approved=False,
            register_issuer=False,
            issuer=IssuerProposal(
                slug=proposal_slug,
                display_name=ctx.issuer_display or "",
                confidence=ctx.classify_result.confidence if ctx.classify_result is not None else 0.0,
                alternatives=[],
            ),
            document=DocumentProposal(
                type=ctx.classify_result.doc_type if ctx.classify_result is not None else "other",
                number=ctx.extract_result.number if ctx.extract_result is not None else None,
                date=ctx.extract_result.date if ctx.extract_result is not None else None,
                title=ctx.extract_result.title if ctx.extract_result is not None else None,
                amount=ctx.extract_result.amount if ctx.extract_result is not None else None,
                currency=ctx.extract_result.currency if ctx.extract_result is not None else None,
                language=ctx.classify_result.language if ctx.classify_result is not None else None,
            ),
            source=SourceProposal(
                kind=ctx.params.source,
                staging_path=ctx.params.staging_path,
                email_msgid=ctx.params.email_msgid,
                email_from=ctx.params.email_from,
                email_subject=ctx.params.email_subject,
                original_filename=ctx.params.original_filename,
                sha256=ctx.sha,
            ),
            ocr=OCRProposal(
                engine=self._settings.ocr.engine,
                languages=list(self._settings.ocr.languages),
                mean_confidence=ctx.ocr_result.mean_confidence or 0.0,
                pages=ctx.ocr_result.pages,
            ),
            triage_reasons=list(ctx.reasons),
            zettel_preview=ZettelPreview(
                id=zk_timestamp,
                title=_compose_triage_title(ctx, doc_type_for_filename),
                ingested_at=datetime.now().astimezone(),
                tags=build_zettel_tags(
                    doc_type_for_filename,
                    slug_for_filename,
                    ctx.extract_result.date if ctx.extract_result is not None else None,
                ),
                summary=ctx.extract_result.summary if ctx.extract_result is not None else None,
            ),
            applied_rule_id=ctx.applied_rule_id,
        )
        write_proposal(proposal_path, proposal)

        # Stamp the raw source sha as seen so a resent copy is caught as a
        # duplicate while the proposal waits for review. Nothing is filed yet,
        # so the row points at the parked _triage PDF.
        self._state_db.record_processed(
            ProcessedRow(
                sha256=ctx.sha,
                canonical_filename=f"_triage/{basename} (pending review)",
                issuer_slug=proposal_slug,
                doc_type=doc_type_for_filename,
                processed_at=datetime.now(timezone.utc),
                extraction_method=_PENDING_TRIAGE_EXTRACTION_METHOD,
            )
        )

        return CommandResult(
            success=True,
            metadata={
                "outcome": IngestOutcome.TRIAGED.value,
                "proposal_path": str(proposal_path),
                "triage_pdf_path": str(triage_pdf),
                "triage_reasons": list(ctx.reasons),
                "sha256": ctx.sha,
            },
        )

    def _write_duplicate_sidecar(self, staging_path: Path, existing_row: ProcessedRow) -> None:
        sidecar_path = staging_path.with_suffix(staging_path.suffix + ".duplicate.yml")
        if existing_row.extraction_method == _PENDING_TRIAGE_EXTRACTION_METHOD:
            comment = "# duplicate detected — this PDF's sha256 matches a document awaiting review in _triage/\n"
        else:
            comment = "# duplicate detected — this PDF's sha256 already maps to a filed document\n"
        content = comment + f"existing_canonical_filename: {existing_row.canonical_filename}\n"
        atomic_write_text(sidecar_path, content)

    def _build_source_metadata(self, params: IngestParams) -> SourceMetadata:
        """Compose the ``SourceMetadata`` shared by the rule engine and classifier.

        Both paths get the full metadata; the classifier internally projects
        it to the user-prompt JSON shape and respects ``doc_type_only`` when
        selecting which fields to expose to the LLM (see
        :func:`_source_metadata_to_prompt_dict`). This is the single source
        of truth for source-metadata construction (previously two parallel
        builders existed; PRD 00034 blind-review I4).
        """
        email_meta = self._load_email_sidecar(params.staging_path)
        return SourceMetadata(
            source_kind=params.source,
            original_filename=params.original_filename or params.staging_path.name,
            email_from=params.email_from or email_meta["email_from"],
            email_subject=params.email_subject or email_meta["email_subject"],
            email_date=email_meta["email_date"],
        )

    def _run_rules(self, ocr_text: str, source_metadata: SourceMetadata, params: IngestParams) -> RuleResult:
        scope = params.issuer_slug_hint if params.source == "issuer-inbox" else None
        engine = RuleEngine()
        return engine.evaluate(
            ocr_text,
            source_metadata,
            self._registry,
            scoped_issuer_slug=scope,
        )

    @staticmethod
    def _load_email_sidecar(staging_path: Path) -> dict[str, str | None]:
        sidecar = staging_path.with_suffix(".email.yml")
        empty: dict[str, str | None] = {"email_from": None, "email_subject": None, "email_date": None}
        if not sidecar.exists():
            return empty

        import yaml

        data = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return empty
        return {
            "email_from": Pipeline._string_or_none(data.get("from")),
            "email_subject": Pipeline._string_or_none(data.get("subject")),
            "email_date": Pipeline._string_or_none(data.get("date")),
        }

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    def _build_extractor_hints(self, params: IngestParams) -> dict[str, str] | None:
        """Compose the hints dict passed to ``Extractor.extract_with_model``.

        The extractor sees only OCR text by default, which loses signals the
        pipeline already has. The original filename of a downloaded invoice
        is often the invoice number itself; the email subject often names
        the document. Surfacing them as hints lets the model fall back on
        them when OCR is noisy or numbers span line breaks.

        Returns ``None`` when there's nothing to surface so the user prompt
        stays clean (no empty 'Hints:' block).
        """
        hints: dict[str, str] = {}
        if params.original_filename:
            hints["original_filename"] = params.original_filename
        if params.email_subject:
            hints["email_subject"] = params.email_subject
        return hints or None

    @staticmethod
    def _zk_timestamp(doc_date: date | None) -> str:
        """14-digit ``YYYYMMDDhhmmss`` timestamp.

        For ingestion-now, uses wall-clock to the second in UTC (matches the
        timezone used by ``state_db.record_processed``). For backfill with a
        known doc_date, uses that date with ``000000`` time per spec §5.
        """
        if doc_date is None:
            return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return doc_date.strftime("%Y%m%d") + "000000"

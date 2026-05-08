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
from typing import TYPE_CHECKING, Any, TypeVar

from buvis.pybase.result import CommandResult

from bim.commands.doc.shared.atomic_write import atomic_write_text
from bim.commands.doc.shared.extractor import IncompleteExtraction
from bim.commands.doc.shared.hashing import sha256_file
from bim.commands.doc.shared.naming import build_canonical_filename, slugify
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
from bim.commands.doc.shared.zettel_helpers import build_zettel_tags, to_tilde_path
from bim.commands.doc.shared.zettel_writer import (
    DocumentZettelFrontmatter,
    build_zettel_body,
)

if TYPE_CHECKING:
    from collections.abc import Callable

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


T = TypeVar("T")


def _retry_llm_call(
    *,
    func: Callable[[str], T],
    primary_model: str,
    fallback_model: str,
    max_retries: int,
    is_transient: Callable[[Exception], bool],
) -> T:
    """Run ``func(model)`` with primary→retries→fallback semantics.

    The pipeline calls into the classifier and extractor through this helper
    so spec §11 retry semantics land in one place:

    - Try ``func(primary_model)`` once.
    - On a transient exception (per ``is_transient``), retry up to
      ``max_retries`` more times against ``primary_model``.
    - On a non-transient exception, re-raise immediately - retries on a
      semantic failure (e.g. unparseable model output) will not help.
    - If all primary attempts raise transient errors, try ``func(fallback_model)``
      once. If the fallback raises (transient or otherwise), re-raise that
      exception unchanged.
    - ``requests.exceptions.Timeout`` is non-retryable by definition (the
      underlying boundary services re-raise it unwrapped); the helper sees it
      as a non-transient via ``is_transient`` returning False, so it bubbles
      out without retry or fallback.
    """
    attempts = 0
    while attempts < 1 + max_retries:
        try:
            return func(primary_model)
        except Exception as exc:
            if not is_transient(exc):
                raise
            attempts += 1

    # All primary attempts exhausted with transient errors. Try fallback once;
    # any exception from it is the final word.
    return func(fallback_model)


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


@dataclass(frozen=True)
class _TriageContext:
    """Snapshot of pipeline state at the moment a triage decision was made.

    Internal helper - not part of the public API. Bundles the inputs needed
    to compose a triage proposal so ``_triage`` keeps a single-arg signature.
    """

    params: IngestParams
    sha: str
    ocr_result: OCRResult
    classify_result: ClassifyResult | None
    extract_result: ExtractResult | None
    reasons: list[str]
    issuer_slug: str
    issuer_display: str


@dataclass(frozen=True)
class _FilingContext:
    """Bundle of inputs threaded into ``_finalize_filing``.

    Keeps the helper signature narrow so ruff PLR0913 stays satisfied while
    the orchestrator delegates the post-extract zettel-build path.
    """

    params: IngestParams
    sha: str
    ocr_result: OCRResult
    classify_result: ClassifyResult
    extract_result: ExtractResult
    issuer_slug: str
    issuer_display: str
    extraction_method: str


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
            self._write_duplicate_sidecar(params.staging_path, dedup.existing_row.canonical_filename)
            return CommandResult(
                success=True,
                metadata={
                    "outcome": IngestOutcome.DUPLICATE.value,
                    "existing_canonical_filename": dedup.existing_row.canonical_filename,
                    "sha256": sha,
                },
            )

        # Step 1b: claim (atomic check-and-reserve)
        if not self._state_db.claim(sha):
            # Another worker already claimed; treat as duplicate from this caller's POV.
            return CommandResult(
                success=True,
                metadata={"outcome": IngestOutcome.DUPLICATE.value, "sha256": sha},
            )

        try:
            return self._run_after_claim(params, sha, active_reporter)
        except Exception as exc:
            # Release the claim so a retry can re-attempt rather than parking forever.
            # Map any escaping exception to a structured CommandResult per AGENTS.md
            # "never let raw exceptions reach the user" - the CLI handler turns
            # success=False into console.failure rather than a stack trace.
            # Capture exception_type/repr alongside stage so log analysis can
            # distinguish failure modes without violating the no-stack-trace rule.
            self._state_db.release_claim(sha)
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

    # --------- internals ---------

    def _run_after_claim(self, params: IngestParams, sha: str, reporter: ProgressReporter) -> CommandResult:
        # Step 2: OCR
        reporter.stage("running OCR")
        ocr_result = self._ocr_runner.run(params.staging_path)

        source_metadata = self._build_rule_source_metadata(params)
        rule_result = self._run_rules(ocr_result.ocr_text, source_metadata, params)
        if rule_result.kind == "conflict":
            return self._triage(
                _TriageContext(
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
            extraction_method = self._rule_extraction_method(rule_result)

        # Step 3: classify
        reporter.stage("classifying document")
        if use_pinned:
            classify_result, classify_error = self._classify_with_pinned(params, ocr_result, rule_result.pinned)
        else:
            classify_result, classify_error = self._classify(params, ocr_result)

        issuer_slug, issuer_display = self._resolve_issuer(params, classify_result)
        triage_reasons = self._collect_classify_triage_reasons(
            classify_error=classify_error,
            classify_result=classify_result,
            issuer_slug=issuer_slug,
        )

        # Without a classify_result there's no doc_type to extract against, so
        # triage immediately. The other triage triggers (unknown issuer, low
        # confidence) still leave us with a usable doc_type, so extraction
        # runs and its output (full or partial) populates the proposal -
        # the human reviewer benefits from seeing what the model did find.
        if classify_result is None:
            return self._triage(
                _TriageContext(
                    params=params,
                    sha=sha,
                    ocr_result=ocr_result,
                    classify_result=None,
                    extract_result=None,
                    reasons=triage_reasons,
                    issuer_slug=issuer_slug,
                    issuer_display=issuer_display,
                )
            )

        # Step 4: extract (with retry+fallback for transient HTTP failures only)
        reporter.stage("extracting fields")

        hints = self._build_extractor_hints(params)

        def _extract_call(model: str) -> ExtractResult:
            if use_pinned:
                return self._extractor.extract_with_pinned(
                    ocr_result.ocr_text,
                    classify_result.doc_type,
                    rule_result.pinned,
                    model=model,
                    hints=hints,
                )
            return self._extractor.extract_with_model(
                ocr_result.ocr_text,
                classify_result.doc_type,
                model=model,
                hints=hints,
            )

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
            # Surface the partial ExtractResult (when present) so the triage
            # proposal shows fields the model did find. exc.partial may be
            # None when no fields could be coerced (e.g. JSON parse error).
            extract_result = exc.partial
            triage_reasons.extend(exc.reasons)
        except Exception as exc:
            # Includes requests.exceptions.Timeout (re-raised unwrapped per Extractor docs).
            triage_reasons.append(f"extractor error: {exc}")

        if triage_reasons or extract_result is None:
            return self._triage(
                _TriageContext(
                    params=params,
                    sha=sha,
                    ocr_result=ocr_result,
                    classify_result=classify_result,
                    extract_result=extract_result,
                    reasons=triage_reasons,
                    issuer_slug=issuer_slug,
                    issuer_display=issuer_display,
                )
            )

        return self._finalize_filing(
            _FilingContext(
                params=params,
                sha=sha,
                ocr_result=ocr_result,
                classify_result=classify_result,
                extract_result=extract_result,
                issuer_slug=issuer_slug,
                issuer_display=issuer_display,
                extraction_method=extraction_method,
            )
        )

    def _finalize_filing(self, ctx: _FilingContext) -> CommandResult:
        """Build the canonical filename, write the zettel, and file the PDF.

        Extracted from ``_run_after_claim`` to keep that orchestrator under
        ruff complexity limits. Triages on slug/filename failures and returns
        the ``CommandResult`` describing the terminal outcome.
        """
        title_or_number = ctx.extract_result.number or ctx.extract_result.title
        if not title_or_number:
            return self._triage(
                _TriageContext(
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
            slug_title = slugify(title_or_number)
        except ValueError:
            return self._triage(
                _TriageContext(
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

        zk_timestamp = self._zk_timestamp(ctx.extract_result.date)
        canonical_filename, zk_timestamp, target_pdf = self._resolve_collision(
            zk_timestamp=zk_timestamp,
            issuer_slug=ctx.issuer_slug,
            title_or_number=slug_title,
            doc_type=ctx.classify_result.doc_type,
        )

        ingest_today = date.today()
        frontmatter = DocumentZettelFrontmatter(
            id=zk_timestamp,
            doc_type=ctx.classify_result.doc_type,
            issuer_slug=ctx.issuer_slug,
            issuer_display=ctx.issuer_display,
            doc_number=ctx.extract_result.number,
            doc_date=ctx.extract_result.date or ingest_today,
            doc_amount=ctx.extract_result.amount,
            doc_currency=ctx.extract_result.currency,
            doc_language=ctx.classify_result.language,
            ingest_date=ingest_today,
            ingest_source=ctx.params.source,
            file_path=to_tilde_path(target_pdf),
            file_sha256=ctx.sha,
            ocr_engine=self._settings.ocr.engine,
            ocr_mean_confidence=ctx.ocr_result.mean_confidence,
            extraction_method=ctx.extraction_method,
            tags=build_zettel_tags(ctx.classify_result.doc_type, ctx.issuer_slug, ctx.extract_result.date),
        )
        body = build_zettel_body(frontmatter, ctx.ocr_result.ocr_text, self._settings.zettel)
        zettel_path = self._zettel_writer.write(frontmatter, body)

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
        # Release the claim once filing has finalised so the claims table
        # doesn't accumulate one orphan row per successfully-filed document.
        # On the happy path the processed row already prevents re-ingestion;
        # the claim row was the in-flight reservation.
        self._state_db.release_claim(ctx.sha)

        return CommandResult(
            success=True,
            metadata={
                "outcome": IngestOutcome.FILED.value,
                "zettel_path": str(zettel_path),
                "pdf_path": str(target_pdf),
                "canonical_filename": canonical_filename,
                "sha256": ctx.sha,
            },
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
        source_metadata = self._build_source_metadata(params, doc_type_only=doc_type_only)

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

        doc_type_only = params.source == "issuer-inbox"
        source_metadata = self._build_source_metadata(params, doc_type_only=doc_type_only)

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

    def _triage(self, ctx: _TriageContext) -> CommandResult:
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
                ingest_date=date.today(),
                tags=build_zettel_tags(
                    doc_type_for_filename,
                    slug_for_filename,
                    ctx.extract_result.date if ctx.extract_result is not None else None,
                ),
            ),
        )
        write_proposal(proposal_path, proposal)

        # Release the claim so a re-run on the same SHA can re-triage cleanly.
        self._state_db.release_claim(ctx.sha)

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

    def _write_duplicate_sidecar(self, staging_path: Path, existing_canonical: str) -> None:
        sidecar_path = staging_path.with_suffix(staging_path.suffix + ".duplicate.yml")
        content = (
            "# duplicate detected — this PDF's sha256 already maps to a filed document\n"
            f"existing_canonical_filename: {existing_canonical}\n"
        )
        atomic_write_text(sidecar_path, content)

    def _build_source_metadata(self, params: IngestParams, *, doc_type_only: bool) -> dict[str, Any]:
        """Compose the dict passed to ``Classifier.classify`` as ``source_metadata``.

        For the ``doc_type_only=True`` path (issuer-inbox), we deliberately
        omit issuer-related hints (original_filename, email_from, email_subject)
        so the prompt stays focused on doc-type identification rather than
        re-classifying the issuer the caller already pinned. This addresses
        the source-metadata-leakage concern deferred from PRD 00030.
        """
        meta: dict[str, Any] = {"source": params.source}
        if doc_type_only:
            return meta
        if params.original_filename:
            meta["original_filename"] = params.original_filename
        if params.email_from:
            meta["email_from"] = params.email_from
        if params.email_subject:
            meta["email_subject"] = params.email_subject
        return meta

    def _run_rules(self, ocr_text: str, source_metadata: SourceMetadata, params: IngestParams) -> RuleResult:
        scope = params.issuer_slug_hint if params.source == "issuer-inbox" else None
        engine = RuleEngine()
        return engine.evaluate(
            ocr_text,
            source_metadata,
            self._registry,
            scoped_issuer_slug=scope,
        )

    def _build_rule_source_metadata(self, params: IngestParams) -> SourceMetadata:
        email_meta = self._load_email_sidecar(params.staging_path)
        return SourceMetadata(
            source_kind=params.source,
            original_filename=params.original_filename or params.staging_path.name,
            email_from=params.email_from or email_meta["email_from"],
            email_subject=params.email_subject or email_meta["email_subject"],
            email_date=email_meta["email_date"],
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

    @staticmethod
    def _rule_extraction_method(rule_result: RuleResult) -> str:
        if rule_result.rule_id is None or rule_result.rule_version is None:
            raise ValueError("matching rule result must include rule id and version")
        prefix = "rule" if rule_result.kind == "full" else "rule+llm"
        return f"{prefix}:{rule_result.rule_id}:v{rule_result.rule_version}"

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

    def _resolve_collision(
        self,
        *,
        zk_timestamp: str,
        issuer_slug: str,
        title_or_number: str,
        doc_type: str,
    ) -> tuple[str, str, Path]:
        """Increment the zk_timestamp seconds field until both target_pdf and
        the future zettel basename are free.

        Spec §11 rows 10/11 mandate a pre-write/pre-move collision check:
        increment the timestamp by one second and retry. The PDF and zettel
        basenames are linked (same canonical stem with .pdf / .md), so a
        single resolved zk_timestamp covers both.

        Caps at 60 attempts (one minute of collisions) and raises
        ``ValueError`` if exhausted - that condition signals a serious clock
        / state-db mismatch worth surfacing rather than silently overwriting.
        """
        candidate_zk = zk_timestamp
        vault_dir = self._settings.paths.vault_root / self._settings.paths.vault_documents_subdir
        for _ in range(60):
            canonical = build_canonical_filename(
                zk_timestamp=candidate_zk,
                issuer_slug=issuer_slug,
                title_or_number=title_or_number,
                doc_type=doc_type,
            )
            target_pdf = self._settings.paths.business_root / issuer_slug / canonical
            zettel_basename = canonical.removesuffix(".pdf") + ".md"
            zettel_path = vault_dir / zettel_basename
            if not target_pdf.exists() and not zettel_path.exists():
                target_pdf.parent.mkdir(parents=True, exist_ok=True)
                return canonical, candidate_zk, target_pdf
            candidate_zk = self._increment_zk_seconds(candidate_zk)
        raise ValueError(f"could not resolve filename collision after 60 attempts starting from {zk_timestamp}")

    @staticmethod
    def _increment_zk_seconds(zk_timestamp: str) -> str:
        """Add one second to a 14-digit zk timestamp with proper rollover."""
        dt = datetime.strptime(zk_timestamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return (dt + timedelta(seconds=1)).strftime("%Y%m%d%H%M%S")

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

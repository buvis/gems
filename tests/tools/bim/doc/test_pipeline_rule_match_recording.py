"""Tests that ``Pipeline._run_ocr_and_rules`` records winning rule matches.

The audit's freshness check reads from ``state_db.rule_matches``. When the
rule engine produces a ``full`` or ``partial`` winner with a non-None
``rule_id``, the pipeline must record ``(rule_id, now_utc)`` so the audit
has data. ``none`` and ``conflict`` outcomes must NOT record anything.

These tests stub ``Pipeline._run_rules`` directly (the engine seam closest
to the recording side effect) and exercise ``_run_ocr_and_rules`` so the
test stays focused on the recording behavior rather than full ingest.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bim.commands.doc.shared.classifier import Classifier
from bim.commands.doc.shared.extractor import Extractor
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.ocr import OCRResult, OCRRunner
from bim.commands.doc.shared.pipeline import Pipeline, PipelineServices
from bim.commands.doc.shared.progress import NoOpProgressReporter
from bim.commands.doc.shared.rules.models import RuleResult
from bim.commands.doc.shared.settings_models import (
    ClassifierSettings,
    DocPaths,
    DocSettings,
    OCRSettings,
    ZettelSettings,
)
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.params.doc_ingest import IngestParams
from buvis.pybase.result import CommandResult
from pytest_mock import MockerFixture


def _make_settings(tmp_path: Path) -> DocSettings:
    paths = DocPaths.model_validate(
        {
            "business_root": str(tmp_path / "Business"),
            "vault_root": str(tmp_path / "Vault"),
            "vault_documents_subdir": "Zettelkasten/documents",
            "state_dir": str(tmp_path / "state"),
        }
    )
    classifier = ClassifierSettings(
        backend="ollama",
        endpoint="http://localhost:11434",
        primary_model="qwen2.5:7b-instruct",
        fallback_model="qwen2.5:14b-instruct",
        triage_threshold=0.85,
        max_retries=2,
    )
    return DocSettings(
        paths=paths,
        ocr=OCRSettings(),
        classifier=classifier,
        zettel=ZettelSettings(),
    )


def _empty_registry() -> IssuerRegistry:
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": list(DOC_TYPES),
            "reserved_slugs": ["unknown", "_triage", "_config"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                },
            },
        }
    )


def _make_ocr_result(pdf_path: Path) -> OCRResult:
    return OCRResult(
        ocr_text="dummy ocr",
        pdf_path=pdf_path,
        was_redone=False,
        original_backup_path=None,
        mean_confidence=0.95,
        pages=1,
    )


def _build_pipeline(
    settings: DocSettings,
    state_db: StateDB,
    mocker: MockerFixture,
    *,
    ocr_result: OCRResult,
    rule_result: RuleResult,
) -> Pipeline:
    ocr_runner = OCRRunner(settings=settings, state_dir=settings.paths.state_dir)
    classifier = Classifier(settings.classifier)
    extractor = Extractor(settings.classifier)
    zettel_writer = ZettelWriter(
        repo=None,
        vault_root=settings.paths.vault_root,
        vault_documents_subdir=settings.paths.vault_documents_subdir,
    )
    mocker.patch.object(ocr_runner, "run", return_value=ocr_result)

    services = PipelineServices(
        state_db=state_db,
        ocr_runner=ocr_runner,
        classifier=classifier,
        extractor=extractor,
        registry=_empty_registry(),
        zettel_writer=zettel_writer,
    )
    pipeline = Pipeline(settings, services)
    mocker.patch.object(pipeline, "_run_rules", return_value=rule_result)
    return pipeline


def _invoke_run_ocr_and_rules(pipeline: Pipeline, staging_pdf: Path) -> object:
    params = IngestParams(source="download", staging_path=staging_pdf)
    return pipeline._run_ocr_and_rules(params, sha="0" * 64, reporter=NoOpProgressReporter())


@pytest.fixture
def settings(tmp_path: Path) -> DocSettings:
    return _make_settings(tmp_path)


@pytest.fixture
def state_db(tmp_path: Path) -> StateDB:
    return StateDB.open(tmp_path / "state" / "state.db")


@pytest.fixture
def staging_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "staging" / "input.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\nfake pdf bytes\n")
    return path


class TestRuleMatchRecording:
    def test_full_rule_match_records_rule_match(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        rule_result = RuleResult(
            kind="full",
            rule_id="r1",
            rule_version=1,
            pinned={"issuer_slug": "cez-as", "doc_type": "invoice"},
        )
        pipeline = _build_pipeline(
            settings,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(staging_pdf),
            rule_result=rule_result,
        )
        before = datetime.now(timezone.utc)
        _invoke_run_ocr_and_rules(pipeline, staging_pdf)
        after = datetime.now(timezone.utc)

        matches = state_db.get_rule_last_matches()
        assert "r1" in matches
        recorded = matches["r1"]
        assert before - timedelta(seconds=5) <= recorded <= after + timedelta(seconds=5)

    def test_partial_rule_match_records_rule_match(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        rule_result = RuleResult(
            kind="partial",
            rule_id="r-partial",
            rule_version=2,
            pinned={"issuer_slug": "cez-as"},
        )
        pipeline = _build_pipeline(
            settings,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(staging_pdf),
            rule_result=rule_result,
        )
        before = datetime.now(timezone.utc)
        _invoke_run_ocr_and_rules(pipeline, staging_pdf)
        after = datetime.now(timezone.utc)

        matches = state_db.get_rule_last_matches()
        assert "r-partial" in matches
        recorded = matches["r-partial"]
        assert before - timedelta(seconds=5) <= recorded <= after + timedelta(seconds=5)

    def test_no_match_does_not_record(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        rule_result = RuleResult(kind="none", rule_id=None, rule_version=None)
        pipeline = _build_pipeline(
            settings,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(staging_pdf),
            rule_result=rule_result,
        )
        _invoke_run_ocr_and_rules(pipeline, staging_pdf)
        assert state_db.get_rule_last_matches() == {}

    def test_conflict_does_not_record(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        rule_result = RuleResult(
            kind="conflict",
            rule_id=None,
            rule_version=None,
            conflicting_rules=["r1", "r2"],
        )
        pipeline = _build_pipeline(
            settings,
            state_db,
            mocker,
            ocr_result=_make_ocr_result(staging_pdf),
            rule_result=rule_result,
        )
        outcome = _invoke_run_ocr_and_rules(pipeline, staging_pdf)
        # Conflict path returns a CommandResult (early-return triage).
        assert isinstance(outcome, CommandResult)
        assert state_db.get_rule_last_matches() == {}

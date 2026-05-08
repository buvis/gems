"""Integration tests for rule-engine wiring inside the bim doc pipeline.

These tests are written against the spec in
``dev/local/prds/wip/00034-bim-doc-rule-engine-v1.md`` (Phase 2 exit criteria
+ Success Metrics) and are expected to FAIL until ``shared/pipeline.py`` is
extended to:

  * insert a rule-engine evaluation between OCR (step 2) and classify (step 3),
  * route by ``RuleResult.kind`` (full / partial / none / conflict),
  * call ``Classifier.classify_with_pinned`` / ``Extractor.extract_with_pinned``
    on full and partial paths (skipping the legacy ``*_with_model`` calls),
  * record ``extraction_method`` as ``rule:<id>:v<n>`` for full,
    ``rule+llm:<id>:v<n>`` for partial, ``llm:<model>`` for none,
  * write a triage proposal carrying ``format_rule_conflict_reason([...])``
    for conflict (no zettel, no LLM).

We mock at the boundary services exactly as ``test_pipeline.py`` does:
``ocr_runner.run`` plus ``classifier.classify_with_model`` /
``extractor.extract_with_model``. The ``*_with_pinned`` variants are mocked on
the partial path so the pipeline can stay LLM-free in the test environment.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from bim.commands.doc.shared.classifier import Classifier, ClassifyResult
from bim.commands.doc.shared.extractor import Extractor, ExtractResult
from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.naming import DOC_TYPES
from bim.commands.doc.shared.ocr import OCRResult, OCRRunner
from bim.commands.doc.shared.pipeline import Pipeline, PipelineServices
from bim.commands.doc.shared.settings_models import (
    ClassifierSettings,
    DocPaths,
    DocSettings,
    OCRSettings,
    ZettelSettings,
)
from bim.commands.doc.shared.state_db import StateDB
from bim.commands.doc.shared.triage import format_rule_conflict_reason, read_proposal
from bim.commands.doc.shared.zettel_writer import ZettelWriter
from bim.params.doc_ingest import IngestParams
from buvis.pybase.result import CommandResult
from pytest_mock import MockerFixture

# ----------------------- helpers (mirrored from test_pipeline.py) -----------------------


def _make_settings(tmp_path: Path, *, triage_threshold: float = 0.85) -> DocSettings:
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
        triage_threshold=triage_threshold,
        max_retries=2,
    )
    return DocSettings(
        paths=paths,
        ocr=OCRSettings(),
        classifier=classifier,
        zettel=ZettelSettings(),
    )


def _write_pdf(path: Path, content: bytes = b"%PDF-1.4\nfake pdf bytes\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _make_ocr_result(text: str, pdf_path: Path) -> OCRResult:
    return OCRResult(
        ocr_text=text,
        pdf_path=pdf_path,
        was_redone=False,
        original_backup_path=None,
        mean_confidence=0.95,
        pages=2,
    )


def _registry_no_rules() -> IssuerRegistry:
    """Issuer registry with cez-as but no ``rules:`` block — baseline behavior."""
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": list(DOC_TYPES),
            "reserved_slugs": ["unknown", "_triage", "_config"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "aliases": ["CEZ", "cez.cz"],
                },
            },
        }
    )


def _cez_full_rule() -> dict[str, Any]:
    """The spec's `cez-invoice-2024-template` rule."""
    return {
        "id": "cez-invoice-2024-template",
        "version": 1,
        "priority": 100,
        "match": {
            "ocr_contains": ["IC: 45274649", "Faktura"],
            "ocr_matches": [r"Faktura č\.\s*(\d{10})"],
        },
        "extract": {
            "issuer_slug": "cez-as",
            "issuer_display": "CEZ a.s.",
            "doc_type": "invoice",
            "doc_number": {
                "from": "ocr_match",
                "pattern": r"Faktura č\.\s*(\d{10})",
                "group": 1,
            },
            "doc_currency": "CZK",
            "doc_language": "cs",
        },
    }


def _cez_partial_rule() -> dict[str, Any]:
    """The spec's `cez-fingerprint` partial rule (pins issuer + language)."""
    return {
        "id": "cez-fingerprint",
        "version": 1,
        "priority": 50,
        "partial": True,
        "match": {
            "ocr_contains": ["IC: 45274649"],
        },
        "extract": {
            "issuer_slug": "cez-as",
            "issuer_display": "CEZ a.s.",
            "doc_language": "cs",
        },
    }


def _registry_with_full_rule() -> IssuerRegistry:
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": list(DOC_TYPES),
            "reserved_slugs": ["unknown", "_triage", "_config"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "aliases": ["CEZ", "cez.cz"],
                    "rules": [_cez_full_rule()],
                },
            },
        }
    )


def _registry_with_partial_rule() -> IssuerRegistry:
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": list(DOC_TYPES),
            "reserved_slugs": ["unknown", "_triage", "_config"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "aliases": ["CEZ", "cez.cz"],
                    "rules": [_cez_partial_rule()],
                },
            },
        }
    )


def _registry_with_conflicting_rules() -> IssuerRegistry:
    """Two partial rules in different issuers, both match, both pin different issuer_slug."""
    rule_cez = {
        "id": "rule-cez",
        "version": 1,
        "priority": 50,
        "partial": True,
        "match": {"ocr_contains": ["Energy bill"]},
        "extract": {
            "issuer_slug": "cez-as",
            "issuer_display": "CEZ a.s.",
        },
    }
    rule_eon = {
        "id": "rule-eon",
        "version": 1,
        "priority": 50,
        "partial": True,
        "match": {"ocr_contains": ["Energy bill"]},
        "extract": {
            "issuer_slug": "eon-cz",
            "issuer_display": "E.ON Czech",
        },
    }
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": list(DOC_TYPES),
            "reserved_slugs": ["unknown", "_triage", "_config"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "rules": [rule_cez],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON Czech",
                    "rules": [rule_eon],
                },
            },
        }
    )


# OCR text matching the spec's two CEZ rules end-to-end.
_CEZ_OCR_TEXT = (
    "Dodavatel: CEZ a.s.\n"
    "IC: 45274649\n"
    "Faktura c. 7102105594\n"
    "Faktura č. 7102105594\n"
    "Datum vystaveni: 11.03.2021\n"
    "Castka: 4218 CZK\n"
)


def _build_pipeline(
    settings: DocSettings,
    registry: IssuerRegistry,
    state_db: StateDB,
    mocker: MockerFixture,
    *,
    ocr_result: OCRResult,
    classify_with_model_return: ClassifyResult | None = None,
    classify_with_model_side_effect: Any = None,
    extract_with_model_return: ExtractResult | None = None,
    extract_with_model_side_effect: Any = None,
    classify_with_pinned_return: ClassifyResult | None = None,
    classify_with_pinned_side_effect: Any = None,
    extract_with_pinned_return: ExtractResult | None = None,
    extract_with_pinned_side_effect: Any = None,
) -> tuple[Pipeline, dict[str, Any]]:
    """Build a Pipeline with OCR + LLM boundaries mocked.

    Defaults assume the legacy LLM methods MUST NOT be called (they raise
    when invoked) so a rule-engine-driven test fails loudly if the pipeline
    falls back to LLM. Override per-test for the no-rules baseline.
    """

    ocr_runner = OCRRunner(settings=settings, state_dir=settings.paths.state_dir)
    classifier = Classifier(settings.classifier)
    extractor = Extractor(settings.classifier)
    zettel_writer = ZettelWriter(
        repo=None,
        vault_root=settings.paths.vault_root,
        vault_documents_subdir=settings.paths.vault_documents_subdir,
    )

    ocr_mock = mocker.patch.object(ocr_runner, "run", return_value=ocr_result)

    # Legacy non-pinned methods. By default they raise so any unintended
    # call during a rule-engine path surfaces as a clear test failure.
    if classify_with_model_side_effect is not None:
        classify_model_mock = mocker.patch.object(
            classifier, "classify_with_model", side_effect=classify_with_model_side_effect
        )
    elif classify_with_model_return is not None:
        classify_model_mock = mocker.patch.object(
            classifier, "classify_with_model", return_value=classify_with_model_return
        )
    else:
        classify_model_mock = mocker.patch.object(
            classifier,
            "classify_with_model",
            side_effect=AssertionError("classify_with_model should not be called when a rule applies"),
        )

    if extract_with_model_side_effect is not None:
        extract_model_mock = mocker.patch.object(
            extractor, "extract_with_model", side_effect=extract_with_model_side_effect
        )
    elif extract_with_model_return is not None:
        extract_model_mock = mocker.patch.object(
            extractor, "extract_with_model", return_value=extract_with_model_return
        )
    else:
        extract_model_mock = mocker.patch.object(
            extractor,
            "extract_with_model",
            side_effect=AssertionError("extract_with_model should not be called when a rule applies"),
        )

    # Pinned variants. By default they also raise so the no-rules path proves
    # nobody accidentally went through the pinned branch.
    if classify_with_pinned_side_effect is not None:
        classify_pinned_mock = mocker.patch.object(
            classifier, "classify_with_pinned", side_effect=classify_with_pinned_side_effect
        )
    elif classify_with_pinned_return is not None:
        classify_pinned_mock = mocker.patch.object(
            classifier, "classify_with_pinned", return_value=classify_with_pinned_return
        )
    else:
        classify_pinned_mock = mocker.patch.object(
            classifier,
            "classify_with_pinned",
            side_effect=AssertionError("classify_with_pinned should not be called without a matching rule"),
        )

    if extract_with_pinned_side_effect is not None:
        extract_pinned_mock = mocker.patch.object(
            extractor, "extract_with_pinned", side_effect=extract_with_pinned_side_effect
        )
    elif extract_with_pinned_return is not None:
        extract_pinned_mock = mocker.patch.object(
            extractor, "extract_with_pinned", return_value=extract_with_pinned_return
        )
    else:
        extract_pinned_mock = mocker.patch.object(
            extractor,
            "extract_with_pinned",
            side_effect=AssertionError("extract_with_pinned should not be called without a matching rule"),
        )

    services = PipelineServices(
        state_db=state_db,
        ocr_runner=ocr_runner,
        classifier=classifier,
        extractor=extractor,
        registry=registry,
        zettel_writer=zettel_writer,
    )
    pipeline = Pipeline(settings, services)
    return pipeline, {
        "ocr": ocr_mock,
        "classify_with_model": classify_model_mock,
        "extract_with_model": extract_model_mock,
        "classify_with_pinned": classify_pinned_mock,
        "extract_with_pinned": extract_pinned_mock,
    }


def _read_zettel_frontmatter(zettel_path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter from a zettel ``.md`` file."""
    text = zettel_path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"zettel missing YAML frontmatter prefix: {text[:40]!r}"
    body = text[len("---\n") :]
    end_index = body.find("\n---\n")
    assert end_index != -1, "zettel frontmatter missing closing fence"
    yaml_block = body[:end_index]
    parsed = yaml.safe_load(yaml_block)
    assert isinstance(parsed, dict)
    return parsed


# ----------------------- fixtures -----------------------


@pytest.fixture
def settings(tmp_path: Path) -> DocSettings:
    return _make_settings(tmp_path)


@pytest.fixture
def state_db(tmp_path: Path) -> StateDB:
    db_path = tmp_path / "state" / "state.db"
    return StateDB.open(db_path)


@pytest.fixture
def staging_pdf(tmp_path: Path) -> Path:
    return _write_pdf(tmp_path / "staging" / "input.pdf")


# ----------------------- 1. No-rules baseline -----------------------


class TestNoRulesBaseline:
    """Empty-rules path must remain byte-identical to the pre-rule-engine pipeline."""

    def test_no_rules_in_registry_uses_llm_path(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(_CEZ_OCR_TEXT, staging_pdf)
        classify_result = ClassifyResult(
            issuer_slug="cez-as",
            issuer_display="CEZ a.s.",
            doc_type="invoice",
            language="cs",
            confidence=0.95,
        )
        extract_result = ExtractResult(
            doc_type="invoice",
            number="7102105594",
            date=date(2021, 3, 11),
            amount=4218.0,
            currency="CZK",
        )
        pipeline, mocks = _build_pipeline(
            settings,
            _registry_no_rules(),
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_with_model_return=classify_result,
            extract_with_model_return=extract_result,
        )
        # Pipeline moves the staged PDF away on the filed path - capture sha
        # before run() so the dedup lookup below can confirm the recorded row.
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert isinstance(result, CommandResult)
        assert result.success is True
        assert result.metadata["outcome"] == "filed"

        # Both legacy LLM methods called exactly once each.
        assert mocks["classify_with_model"].call_count >= 1
        assert mocks["extract_with_model"].call_count >= 1

        # Pinned variants must NOT be called when no rule is in the registry.
        mocks["classify_with_pinned"].assert_not_called()
        mocks["extract_with_pinned"].assert_not_called()

        zettel_path = Path(result.metadata["zettel_path"])
        frontmatter = _read_zettel_frontmatter(zettel_path)
        assert frontmatter["extraction-method"] == f"llm:{settings.classifier.primary_model}"

        row = state_db.dedup(sha)
        assert row.is_duplicate is True
        assert row.existing_row is not None
        assert row.existing_row.extraction_method == f"llm:{settings.classifier.primary_model}"


# ----------------------- 2. Full rule short-circuits LLM -----------------------


class TestFullRuleShortCircuit:
    """A matching full rule must skip the legacy LLM path entirely."""

    def test_full_rule_files_with_rule_extraction_method(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(_CEZ_OCR_TEXT, staging_pdf)
        # The full rule pins issuer/doc_type/language entirely. The classifier's
        # ``classify_with_pinned`` "full skip" branch synthesizes the result
        # without calling Ollama; the extractor's pinned method copies all
        # required invoice fields verbatim. Mocks return matching synthetic
        # results so the pipeline can reach the "filed" terminal path.
        synthetic_classify = ClassifyResult(
            issuer_slug="cez-as",
            issuer_display="CEZ a.s.",
            doc_type="invoice",
            language="cs",
            confidence=1.0,
        )
        synthetic_extract = ExtractResult(
            doc_type="invoice",
            number="7102105594",
            date=date(2021, 3, 11),
            amount=4218.0,
            currency="CZK",
        )
        pipeline, mocks = _build_pipeline(
            settings,
            _registry_with_full_rule(),
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_with_pinned_return=synthetic_classify,
            extract_with_pinned_return=synthetic_extract,
        )
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"

        # Legacy non-pinned methods MUST NOT be called when the full rule fires.
        mocks["classify_with_model"].assert_not_called()
        mocks["extract_with_model"].assert_not_called()

        zettel_path = Path(result.metadata["zettel_path"])
        frontmatter = _read_zettel_frontmatter(zettel_path)
        assert frontmatter["extraction-method"] == "rule:cez-invoice-2024-template:v1"
        # v1: slug lives in tags, not as a top-level frontmatter field.
        assert "issuer/cez-as" in frontmatter["tags"]
        assert frontmatter["doc-type"] == "invoice"

        row = state_db.dedup(sha)
        assert row.existing_row is not None
        assert row.existing_row.extraction_method == "rule:cez-invoice-2024-template:v1"


# ----------------------- 3. Partial rule reduces LLM scope -----------------------


class TestPartialRuleReducesScope:
    """A matching partial rule must call ``*_with_pinned`` (and not the legacy methods)."""

    def test_partial_rule_files_with_rule_plus_llm_extraction_method(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_result = _make_ocr_result(_CEZ_OCR_TEXT, staging_pdf)
        # Partial rule pins issuer_slug, issuer_display, doc_language. The LLM
        # is asked only for doc_type + the canonical extraction fields.
        synthetic_classify = ClassifyResult(
            issuer_slug="cez-as",
            issuer_display="CEZ a.s.",
            doc_type="invoice",
            language="cs",
            confidence=1.0,
        )
        synthetic_extract = ExtractResult(
            doc_type="invoice",
            number="7102105594",
            date=date(2021, 3, 11),
            amount=4218.0,
            currency="CZK",
        )
        pipeline, mocks = _build_pipeline(
            settings,
            _registry_with_partial_rule(),
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_with_pinned_return=synthetic_classify,
            extract_with_pinned_return=synthetic_extract,
        )
        sha = hashlib.sha256(staging_pdf.read_bytes()).hexdigest()
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"

        # Legacy methods must NOT fire on the partial path.
        mocks["classify_with_model"].assert_not_called()
        mocks["extract_with_model"].assert_not_called()
        # Pinned methods are the actual LLM seam now.
        assert mocks["classify_with_pinned"].call_count >= 1
        assert mocks["extract_with_pinned"].call_count >= 1

        zettel_path = Path(result.metadata["zettel_path"])
        frontmatter = _read_zettel_frontmatter(zettel_path)
        assert frontmatter["extraction-method"] == "rule+llm:cez-fingerprint:v1"
        assert "issuer/cez-as" in frontmatter["tags"]
        assert frontmatter["doc-language"] == "cs"

        row = state_db.dedup(sha)
        assert row.existing_row is not None
        assert row.existing_row.extraction_method == "rule+llm:cez-fingerprint:v1"

    def test_partial_rule_passes_pinned_dict_to_classifier(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        """The pinned dict from the rule engine must reach ``classify_with_pinned``."""
        ocr_result = _make_ocr_result(_CEZ_OCR_TEXT, staging_pdf)
        synthetic_classify = ClassifyResult(
            issuer_slug="cez-as",
            issuer_display="CEZ a.s.",
            doc_type="invoice",
            language="cs",
            confidence=1.0,
        )
        synthetic_extract = ExtractResult(
            doc_type="invoice",
            number="7102105594",
            date=date(2021, 3, 11),
            amount=4218.0,
            currency="CZK",
        )
        pipeline, mocks = _build_pipeline(
            settings,
            _registry_with_partial_rule(),
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_with_pinned_return=synthetic_classify,
            extract_with_pinned_return=synthetic_extract,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)
        assert result.success is True

        # The classifier's pinned method must have seen the rule's pinned dict
        # somewhere in the call (positional or keyword). The fingerprint rule
        # pins issuer_slug=cez-as.
        seen_pinned: dict[str, object] | None = None
        for call in mocks["classify_with_pinned"].call_args_list:
            for value in list(call.args) + list(call.kwargs.values()):
                if isinstance(value, dict) and value.get("issuer_slug") == "cez-as":
                    seen_pinned = value
                    break
            if seen_pinned is not None:
                break
        assert seen_pinned is not None, (
            f"classify_with_pinned never received a pinned dict with issuer_slug=cez-as; "
            f"calls were: {mocks['classify_with_pinned'].call_args_list!r}"
        )
        assert seen_pinned.get("issuer_display") == "CEZ a.s."
        assert seen_pinned.get("doc_language") == "cs"


# ----------------------- 4. Conflict triages -----------------------


class TestRuleConflictTriages:
    """Two rules from different issuers disagreeing on issuer_slug → triage, no LLM."""

    def test_conflict_writes_triage_with_format_rule_conflict_reason(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_text = "Energy bill summary for the period.\n"
        ocr_result = _make_ocr_result(ocr_text, staging_pdf)
        # All four LLM-bound entry points default to raising AssertionError so
        # the test fails loudly if the pipeline reaches any of them on conflict.
        pipeline, mocks = _build_pipeline(
            settings,
            _registry_with_conflicting_rules(),
            state_db,
            mocker,
            ocr_result=ocr_result,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "triaged"

        # No LLM seam should have been touched on the conflict path.
        mocks["classify_with_model"].assert_not_called()
        mocks["extract_with_model"].assert_not_called()
        mocks["classify_with_pinned"].assert_not_called()
        mocks["extract_with_pinned"].assert_not_called()

        expected_reason = format_rule_conflict_reason(["rule-cez", "rule-eon"])
        triage_reasons = result.metadata["triage_reasons"]
        assert expected_reason in triage_reasons, (
            f"expected {expected_reason!r} in triage_reasons; got {triage_reasons!r}"
        )

        proposal_path = Path(result.metadata["proposal_path"])
        proposal = read_proposal(proposal_path)
        assert expected_reason in proposal.triage_reasons

    def test_conflict_does_not_write_zettel(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_text = "Energy bill summary for the period.\n"
        ocr_result = _make_ocr_result(ocr_text, staging_pdf)
        pipeline, _ = _build_pipeline(
            settings,
            _registry_with_conflicting_rules(),
            state_db,
            mocker,
            ocr_result=ocr_result,
        )
        params = IngestParams(source="download", staging_path=staging_pdf)
        result = pipeline.run(params)

        assert result.metadata["outcome"] == "triaged"
        # No zettel path should be returned when conflict triages.
        assert "zettel_path" not in result.metadata

        # The vault directory should be empty (or non-existent).
        vault_docs = settings.paths.vault_root / settings.paths.vault_documents_subdir
        if vault_docs.exists():
            assert list(vault_docs.glob("*.md")) == []


# ----------------------- 5. Edge: issuer-inbox source scoping -----------------------


class TestIssuerInboxScoping:
    """For the ``issuer-inbox`` source kind, only the hinted issuer's rules are evaluated.

    A would-otherwise-conflicting rule on a different issuer must be skipped
    when ``params.issuer_slug_hint`` pins the engine scope. This proves the
    pipeline forwards ``scoped_issuer_slug`` to ``RuleEngine.evaluate``.
    """

    def test_issuer_inbox_scopes_engine_to_hinted_issuer(
        self,
        settings: DocSettings,
        state_db: StateDB,
        staging_pdf: Path,
        mocker: MockerFixture,
    ) -> None:
        ocr_text = "Energy bill summary for the period.\n"
        ocr_result = _make_ocr_result(ocr_text, staging_pdf)

        synthetic_classify = ClassifyResult(
            issuer_slug="cez-as",
            issuer_display="CEZ a.s.",
            doc_type="invoice",
            language="cs",
            confidence=1.0,
        )
        synthetic_extract = ExtractResult(
            doc_type="invoice",
            number="ENERGY-001",
            date=date(2024, 1, 15),
            amount=100.0,
            currency="CZK",
        )

        pipeline, mocks = _build_pipeline(
            settings,
            _registry_with_conflicting_rules(),
            state_db,
            mocker,
            ocr_result=ocr_result,
            classify_with_pinned_return=synthetic_classify,
            extract_with_pinned_return=synthetic_extract,
        )
        # Same OCR text that would be a conflict with two issuers in scope,
        # but issuer-inbox pins us to cez-as → only rule-cez is evaluated →
        # partial match → filed (no triage).
        params = IngestParams(
            source="issuer-inbox",
            staging_path=staging_pdf,
            issuer_slug_hint="cez-as",
        )
        result = pipeline.run(params)

        assert result.success is True
        assert result.metadata["outcome"] == "filed"
        # Pinned variants only — no legacy LLM call, no triage.
        mocks["classify_with_model"].assert_not_called()
        mocks["extract_with_model"].assert_not_called()

        zettel_path = Path(result.metadata["zettel_path"])
        frontmatter = _read_zettel_frontmatter(zettel_path)
        assert frontmatter["extraction-method"] == "rule+llm:rule-cez:v1"
        assert "issuer/cez-as" in frontmatter["tags"]

from __future__ import annotations

from pathlib import Path

import pytest
from bim.params.doc_ingest import IngestParams
from bim.params.doc_promote import PromoteParams
from pydantic import ValidationError


class TestIngestParams:
    def test_required_fields_only(self) -> None:
        p = IngestParams(source="scan", staging_path=Path("/tmp/x.pdf"))
        assert p.source == "scan"
        assert p.staging_path == Path("/tmp/x.pdf")
        assert p.original_filename is None
        assert p.email_msgid is None
        assert p.email_from is None
        assert p.email_subject is None
        assert p.issuer_slug_hint is None
        assert p.dry_run is False

    def test_all_optional_fields(self) -> None:
        p = IngestParams(
            source="email",
            staging_path=Path("/tmp/x.pdf"),
            original_filename="invoice.pdf",
            email_msgid="<abc@vendor.cz>",
            email_from="noreply@vendor.cz",
            email_subject="Faktura 02/2026",
            issuer_slug_hint="cez-as",
            dry_run=True,
        )
        assert p.email_msgid == "<abc@vendor.cz>"
        assert p.dry_run is True

    @pytest.mark.parametrize(
        "source",
        [
            "email",
            "scan",
            "download",
            "issuer-inbox",
            "backfill-canonical",
            "backfill-noncanonical",
        ],
    )
    def test_all_valid_sources(self, source: str) -> None:
        p = IngestParams.model_validate({"source": source, "staging_path": "/tmp/x.pdf"})
        assert p.source == source

    def test_invalid_source_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestParams.model_validate({"source": "bogus", "staging_path": "/tmp/x.pdf"})

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IngestParams.model_validate({"source": "scan", "staging_path": "/tmp/x.pdf", "unknown": 1})

    def test_frozen(self) -> None:
        p = IngestParams(source="scan", staging_path=Path("/tmp/x.pdf"))
        with pytest.raises(ValidationError):
            p.dry_run = True

    def test_missing_source_raises(self) -> None:
        with pytest.raises(ValidationError):
            IngestParams.model_validate({"staging_path": "/tmp/x.pdf"})

    def test_missing_staging_path_raises(self) -> None:
        with pytest.raises(ValidationError):
            IngestParams.model_validate({"source": "scan"})


class TestPromoteParams:
    def test_required_fields_only(self) -> None:
        p = PromoteParams(proposed_yml_path=Path("/tmp/x.proposed.yml"))
        assert p.proposed_yml_path == Path("/tmp/x.proposed.yml")
        assert p.dry_run is False

    def test_dry_run_true(self) -> None:
        p = PromoteParams(proposed_yml_path=Path("/tmp/x.proposed.yml"), dry_run=True)
        assert p.dry_run is True

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PromoteParams.model_validate({"proposed_yml_path": "/tmp/x.proposed.yml", "unknown": 1})

    def test_frozen(self) -> None:
        p = PromoteParams(proposed_yml_path=Path("/tmp/x.proposed.yml"))
        with pytest.raises(ValidationError):
            p.dry_run = True

    def test_missing_path_raises(self) -> None:
        with pytest.raises(ValidationError):
            PromoteParams.model_validate({})

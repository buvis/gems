from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from bim.commands.doc.shared.issuers import IssuerEntry, IssuerRegistry
from bim.commands.doc.shared.triage import (
    DocumentProposal,
    IssuerProposal,
    OCRProposal,
    SourceProposal,
    TriageProposal,
    ZettelPreview,
    read_proposal,
    validate_for_promote,
    write_proposal,
)


def _full_proposal() -> TriageProposal:
    return TriageProposal(
        approved=False,
        register_issuer=False,
        issuer=IssuerProposal(
            slug="cez-as",
            display_name="CEZ a.s.",
            confidence=0.62,
            alternatives=[{"slug": "cez-prodej", "score": 0.31}],
        ),
        document=DocumentProposal(
            type="invoice",
            number="7102105594",
            date=date(2021, 3, 11),
            title=None,
            amount=4218,
            currency="CZK",
            language="cs",
        ),
        source=SourceProposal(
            kind="email",
            staging_path=Path("/tmp/staging/abc.pdf"),
            email_msgid="<abc@vendor.cz>",
            email_from="noreply@cez.cz",
            email_subject="Vyuctovani 02/2021",
            original_filename="invoice_7102105594.pdf",
            sha256="3f4a8c2b" * 8,
        ),
        ocr=OCRProposal(
            engine="tesseract",
            languages=["ces", "eng"],
            mean_confidence=0.91,
            pages=2,
        ),
        triage_reasons=["issuer confidence below threshold"],
        zettel_preview=ZettelPreview(
            id="20260504093422",
            ingest_date=date(2026, 5, 4),
            tags=["document/invoice", "issuer/cez-as", "year/2021"],
        ),
    )


def _registry_with(*issuer_slugs: str) -> IssuerRegistry:
    return IssuerRegistry(
        version=1,
        doc_types=[
            "invoice",
            "receipt",
            "statement",
            "contract",
            "certificate",
            "reminder",
            "correspondence",
            "other",
        ],
        reserved_slugs=["unknown", "_triage", "_config"],
        issuers={slug: IssuerEntry(slug=slug, display_name=slug) for slug in issuer_slugs},
    )


class TestRoundTrip:
    def test_write_then_read_returns_equal(self, tmp_path: Path) -> None:
        path = tmp_path / "proposal.proposed.yml"
        proposal = _full_proposal()
        write_proposal(path, proposal)

        loaded = read_proposal(path)
        assert loaded == proposal


class TestAtomicWrite:
    def test_replace_failure_leaves_target_untouched(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import os

        target = tmp_path / "proposal.proposed.yml"
        target.write_text("ORIGINAL\n", encoding="utf-8")
        original_content = target.read_text(encoding="utf-8")

        def boom(*args: object, **kwargs: object) -> None:
            raise OSError("replace fails")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError, match="replace fails"):
            write_proposal(target, _full_proposal())

        assert target.read_text(encoding="utf-8") == original_content
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == []


class TestValidateForPromote:
    def test_unapproved_fails(self) -> None:
        proposal = _full_proposal()
        registry = _registry_with("cez-as")
        errors = validate_for_promote(proposal, registry)
        assert any("approved" in e for e in errors)

    def test_unknown_issuer_without_register_fails(self) -> None:
        proposal = _full_proposal().model_copy(update={"approved": True})
        registry = _registry_with("other-issuer")
        errors = validate_for_promote(proposal, registry)
        assert any("registry" in e or "register_issuer" in e for e in errors)

    def test_unknown_issuer_with_register_passes(self) -> None:
        proposal = _full_proposal().model_copy(update={"approved": True, "register_issuer": True})
        registry = _registry_with("other-issuer")
        errors = validate_for_promote(proposal, registry)
        assert all("registry" not in e for e in errors)
        assert all("register_issuer" not in e for e in errors)

    def test_unknown_doc_type_fails(self) -> None:
        bad_doc = _full_proposal().document.model_copy(update={"type": "bogus"})
        proposal = _full_proposal().model_copy(update={"approved": True, "document": bad_doc})
        registry = _registry_with("cez-as")
        errors = validate_for_promote(proposal, registry)
        assert any("doc_type" in e or "type" in e for e in errors)

    def test_missing_number_and_title_fails(self) -> None:
        bad_doc = _full_proposal().document.model_copy(update={"number": None, "title": None})
        proposal = _full_proposal().model_copy(update={"approved": True, "document": bad_doc})
        registry = _registry_with("cez-as")
        errors = validate_for_promote(proposal, registry)
        assert any("title" in e.lower() or "number" in e.lower() for e in errors)

    def test_happy_path_existing_issuer(self) -> None:
        proposal = _full_proposal().model_copy(update={"approved": True})
        registry = _registry_with("cez-as")
        errors = validate_for_promote(proposal, registry)
        assert errors == []

    def test_happy_path_new_issuer(self) -> None:
        proposal = _full_proposal().model_copy(update={"approved": True, "register_issuer": True})
        registry = _registry_with("other-issuer")
        errors = validate_for_promote(proposal, registry)
        assert errors == []

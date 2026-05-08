from __future__ import annotations

from typing import Any

from bim.commands.doc.shared.issuers import IssuerRegistry
from bim.commands.doc.shared.rules.engine import RuleEngine
from bim.commands.doc.shared.rules.models import RuleResult, SourceMetadata

__all__ = [
    "_CEZ_OCR",
    "IssuerRegistry",
    "RuleEngine",
    "RuleResult",
    "_cez_full_rule",
    "_cez_partial_rule",
    "_empty_registry",
    "_registry",
    "_source",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source(
    *,
    source_kind: str = "filesystem",
    original_filename: str | None = None,
    email_from: str | None = None,
    email_subject: str | None = None,
    email_date: str | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_kind=source_kind,
        original_filename=original_filename,
        email_from=email_from,
        email_subject=email_subject,
        email_date=email_date,
    )


def _registry(issuers: dict[str, dict[str, Any]]) -> IssuerRegistry:
    """Build an ``IssuerRegistry`` from a compact dict, filling stable defaults."""
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": ["invoice", "receipt", "statement", "other"],
            "reserved_slugs": ["unknown", "_triage", "_config"],
            "issuers": issuers,
        }
    )


def _empty_registry() -> IssuerRegistry:
    return _registry({})


def _cez_full_rule(*, rule_id: str = "cez-invoice-2024-template", priority: int = 100) -> dict[str, Any]:
    return {
        "id": rule_id,
        "version": 1,
        "priority": priority,
        "match": {
            "ocr_contains": ["IC: 45274649", "Faktura"],
            "ocr_matches": [r"Faktura č\.\s*(\d{10})"],
        },
        "extract": {
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


def _cez_partial_rule(*, rule_id: str = "cez-fingerprint", priority: int = 50) -> dict[str, Any]:
    return {
        "id": rule_id,
        "version": 1,
        "priority": priority,
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


_CEZ_OCR = "Dodavatel: CEZ a.s.\nIC: 45274649\nFaktura č. 1234567890\nDatum vystaveni: 01.06.2024\n"

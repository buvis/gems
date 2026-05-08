"""Tests for the bim doc rules test command class."""

from __future__ import annotations

from pathlib import Path

from bim.commands.doc.shared.issuers import IssuerRegistry


def _registry_with_rule() -> IssuerRegistry:
    return IssuerRegistry.model_validate(
        {
            "version": 1,
            "doc_types": ["invoice"],
            "reserved_slugs": ["unknown"],
            "issuers": {
                "cez-as": {
                    "slug": "cez-as",
                    "display_name": "CEZ a.s.",
                    "aliases": [],
                    "rules": [
                        {
                            "id": "cez-fingerprint",
                            "partial": True,
                            "match": {"ocr_contains": ["IC: 45274649"]},
                            "extract": {
                                "issuer_slug": "cez-as",
                                "issuer_display": "CEZ a.s.",
                            },
                        },
                    ],
                },
            },
        }
    )


class _StubOCRRunner:
    """Stand-in for `OCRRunner` that returns canned text without subprocess."""

    def __init__(self, ocr_text: str) -> None:
        self._ocr_text = ocr_text
        self.calls = 0

    def run(self, pdf_path: Path):
        from bim.commands.doc.shared.ocr import OCRResult

        self.calls += 1
        return OCRResult(
            ocr_text=self._ocr_text,
            pdf_path=pdf_path,
            was_redone=False,
            original_backup_path=None,
            mean_confidence=0.9,
            pages=1,
        )


class TestRulesTestCommandRuleNotFound:
    def test_unknown_rule_id(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.test import CommandRulesTest

        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        ocr = _StubOCRRunner("...")
        result = CommandRulesTest(ocr_runner=ocr).run(_registry_with_rule(), "no-such-rule", pdf)
        assert result.success is False
        assert "no-such-rule" in (result.error or "")
        assert ocr.calls == 0


class TestRulesTestCommandMatch:
    def test_match_on_full_pdf_path(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.test import CommandRulesTest

        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        ocr = _StubOCRRunner("Vendor IC: 45274649\nFaktura\n")
        result = CommandRulesTest(ocr_runner=ocr).run(_registry_with_rule(), "cez-fingerprint", pdf)
        assert result.success is True
        output = (result.output or "").upper()
        assert "MATCH" in output
        body = result.output or ""
        assert "cez-as" in body
        assert ocr.calls == 1


class TestRulesTestCommandNoMatch:
    def test_no_match_returns_failure(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.test import CommandRulesTest

        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        ocr = _StubOCRRunner("Unrelated text without the IC value")
        result = CommandRulesTest(ocr_runner=ocr).run(_registry_with_rule(), "cez-fingerprint", pdf)
        assert result.success is False
        text = (result.error or "") + (result.output or "")
        assert "NO MATCH" in text.upper() or "no match" in text.lower()


class TestRulesTestCommandFileMissing:
    def test_missing_pdf(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.test import CommandRulesTest

        ocr = _StubOCRRunner("...")
        result = CommandRulesTest(ocr_runner=ocr).run(_registry_with_rule(), "cez-fingerprint", tmp_path / "nope.pdf")
        assert result.success is False
        assert ocr.calls == 0

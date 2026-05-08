"""Tests for the bim doc rules backtest command class."""

from __future__ import annotations

from pathlib import Path

from bim.commands.doc.shared.issuers import IssuerRegistry


def _registry() -> IssuerRegistry:
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
                            "extract": {"issuer_slug": "cez-as", "issuer_display": "CEZ a.s."},
                        },
                    ],
                },
                "eon-cz": {
                    "slug": "eon-cz",
                    "display_name": "E.ON",
                    "aliases": [],
                    "rules": [
                        {
                            "id": "eon-fingerprint",
                            "partial": True,
                            "match": {"ocr_contains": ["IC: 25733591"]},
                            "extract": {"issuer_slug": "eon-cz"},
                        },
                    ],
                },
            },
        }
    )


class _StubOCRRunner:
    def __init__(self, text_by_name: dict[str, str]) -> None:
        self._mapping = text_by_name
        self.calls = 0

    def run(self, pdf_path: Path):
        from bim.commands.doc.shared.ocr import OCRResult

        self.calls += 1
        text = self._mapping.get(pdf_path.name, "")
        return OCRResult(
            ocr_text=text,
            pdf_path=pdf_path,
            was_redone=False,
            original_backup_path=None,
            mean_confidence=0.9,
            pages=1,
        )


def _seed_archive(business_root: Path, layout: dict[str, list[str]]) -> None:
    for slug, files in layout.items():
        issuer_dir = business_root / slug
        issuer_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            (issuer_dir / name).write_bytes(b"%PDF-1.4\n")


class TestBacktestCommandEmpty:
    def test_empty_archive(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.backtest import CommandRulesBacktest

        ocr = _StubOCRRunner({})
        result = CommandRulesBacktest(ocr_runner=ocr).run(_registry(), tmp_path / "Business")
        assert result.success is True
        assert "0" in (result.output or "")


class TestBacktestCommandHappyPath:
    def test_match_in_owning_folder_no_warning(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.backtest import CommandRulesBacktest

        business = tmp_path / "Business"
        _seed_archive(business, {"cez-as": ["one.pdf", "two.pdf"]})
        ocr = _StubOCRRunner({"one.pdf": "Vendor IC: 45274649\n", "two.pdf": "Vendor IC: 45274649\n"})
        result = CommandRulesBacktest(ocr_runner=ocr).run(_registry(), business)
        assert result.success is True
        out = result.output or ""
        assert "cez-fingerprint" in out
        assert "cez-as" in out


class TestBacktestCommandCrossFolderWarning:
    def test_match_in_other_issuer_folder_flagged(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.backtest import CommandRulesBacktest

        business = tmp_path / "Business"
        _seed_archive(business, {"eon-cz": ["mystery.pdf"]})
        ocr = _StubOCRRunner({"mystery.pdf": "Bogus IC: 45274649\n"})
        result = CommandRulesBacktest(ocr_runner=ocr).run(_registry(), business)
        assert result.success is True
        out = result.output or ""
        assert "cez-fingerprint" in out
        assert "unexpected" in out.lower() or "⚠" in out


class TestBacktestCommandFilters:
    def test_rule_filter_unknown_id(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.backtest import CommandRulesBacktest

        business = tmp_path / "Business"
        _seed_archive(business, {"cez-as": []})
        ocr = _StubOCRRunner({})
        result = CommandRulesBacktest(ocr_runner=ocr).run(_registry(), business, rule_id="no-such-rule")
        assert result.success is False

    def test_issuer_filter_restricts_rule_pool(self, tmp_path: Path) -> None:
        from bim.commands.doc.rules.backtest import CommandRulesBacktest

        business = tmp_path / "Business"
        _seed_archive(business, {"cez-as": ["a.pdf"], "eon-cz": ["b.pdf"]})
        ocr = _StubOCRRunner({"a.pdf": "IC: 45274649\n", "b.pdf": "IC: 25733591\n"})
        result = CommandRulesBacktest(ocr_runner=ocr).run(_registry(), business, issuer_slug="cez-as")
        assert result.success is True
        out = result.output or ""
        assert "cez-fingerprint" in out
        assert "eon-fingerprint" not in out

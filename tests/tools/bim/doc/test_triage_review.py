"""Tests for ``CommandTriageList`` / ``CommandTriageApprove`` (PRD 00057)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from bim.commands.doc.triage.triage import (
    CommandTriageApprove,
    CommandTriageList,
    TriageApproveServices,
    TriageListServices,
)
from bim.params.doc_triage import TriageApproveParams, TriageListParams
from buvis.pybase.result import CommandResult


def _proposal_yaml(*, approved: bool = False, issuer: str = "cez-as") -> str:
    payload = {
        "approved": approved,
        "register_issuer": False,
        "issuer": {"slug": issuer, "display_name": "ČEZ a.s.", "confidence": 0.9, "alternatives": []},
        "document": {"type": "invoice", "number": "7102105594", "date": "2021-03-11", "title": "invoice"},
        "source": {"kind": "email", "staging_path": "/x.pdf", "sha256": "a" * 64},
        "ocr": {"engine": "tesseract", "languages": ["ces"], "mean_confidence": 0.9, "pages": 1},
        "triage_reasons": ["low_confidence"],
        "zettel_preview": {
            "id": "20210311083422",
            "title": "invoice",
            "ingested_at": "2026-05-04T14:30:22+02:00",
            "tags": ["document/invoice"],
        },
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def _write_proposal(triage_dir: Path, name: str, **kwargs: object) -> Path:
    triage_dir.mkdir(parents=True, exist_ok=True)
    path = triage_dir / name
    path.write_text(_proposal_yaml(**kwargs), encoding="utf-8")
    return path


class TestCommandTriageList:
    def test_lists_pending_proposals(self, tmp_path: Path) -> None:
        business_root = tmp_path / "Business"
        triage_dir = business_root / "_triage"
        _write_proposal(triage_dir, "a.pdf.proposed.yml")
        _write_proposal(triage_dir, "b.pdf.proposed.yml", issuer="o2")
        # a non-proposal file is ignored
        (triage_dir / "note.txt").write_text("ignore me", encoding="utf-8")

        cmd = CommandTriageList(services=TriageListServices(business_root=business_root), params=TriageListParams())
        result = cmd.execute()

        assert result.success
        assert result.metadata["count"] == 2
        slugs = {p["issuer_slug"] for p in result.metadata["proposals"]}
        assert slugs == {"cez-as", "o2"}
        row = result.metadata["proposals"][0]
        assert row["doc_type"] == "invoice"
        assert row["triage_reasons"] == ["low_confidence"]
        assert row["path"].endswith(".proposed.yml")

    def test_empty_when_no_triage_dir(self, tmp_path: Path) -> None:
        cmd = CommandTriageList(
            services=TriageListServices(business_root=tmp_path / "Business"),
            params=TriageListParams(),
        )
        result = cmd.execute()
        assert result.success
        assert result.metadata["count"] == 0

    def test_unparseable_proposal_is_reported_not_fatal(self, tmp_path: Path) -> None:
        business_root = tmp_path / "Business"
        triage_dir = business_root / "_triage"
        _write_proposal(triage_dir, "good.pdf.proposed.yml")
        triage_dir.joinpath("bad.pdf.proposed.yml").write_text("::: not yaml :::", encoding="utf-8")

        cmd = CommandTriageList(services=TriageListServices(business_root=business_root), params=TriageListParams())
        result = cmd.execute()

        assert result.success
        assert result.metadata["count"] == 1
        assert any("bad.pdf.proposed.yml" in w for w in result.warnings)


class TestCommandTriageApprove:
    def _services(self) -> TriageApproveServices:
        return TriageApproveServices(settings=MagicMock(), promote_services=MagicMock())

    def test_sets_approved_and_promotes(self, tmp_path: Path) -> None:
        triage_dir = tmp_path / "Business" / "_triage"
        proposal = _write_proposal(triage_dir, "x.pdf.proposed.yml", approved=False)

        promoted = CommandResult(success=True, metadata={"zettel_path": "/z.md", "pdf_path": "/p.pdf"})
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = promoted

        with patch("bim.commands.doc.promote.promote.CommandPromote", return_value=cmd_mock) as mk:
            result = CommandTriageApprove(
                services=self._services(),
                params=TriageApproveParams(proposed_yml_path=proposal),
            ).execute()

        assert result.success
        # the on-disk proposal was flipped to approved before promote ran
        data = yaml.safe_load(proposal.read_text(encoding="utf-8"))
        assert data["approved"] is True
        mk.assert_called_once()

    def test_already_approved_promotes_without_rewrite(self, tmp_path: Path) -> None:
        triage_dir = tmp_path / "Business" / "_triage"
        proposal = _write_proposal(triage_dir, "x.pdf.proposed.yml", approved=True)
        before_mtime = proposal.stat().st_mtime_ns

        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = CommandResult(success=True)
        with patch("bim.commands.doc.promote.promote.CommandPromote", return_value=cmd_mock):
            result = CommandTriageApprove(
                services=self._services(),
                params=TriageApproveParams(proposed_yml_path=proposal),
            ).execute()

        assert result.success
        # not rewritten (already approved)
        assert proposal.stat().st_mtime_ns == before_mtime

    def test_missing_proposal_returns_failure(self, tmp_path: Path) -> None:
        result = CommandTriageApprove(
            services=self._services(),
            params=TriageApproveParams(proposed_yml_path=tmp_path / "nope.pdf.proposed.yml"),
        ).execute()
        assert not result.success
        assert "not found" in (result.error or "")

    def test_non_proposal_suffix_returns_failure(self, tmp_path: Path) -> None:
        other = tmp_path / "note.md"
        other.write_text("x", encoding="utf-8")
        result = CommandTriageApprove(
            services=self._services(),
            params=TriageApproveParams(proposed_yml_path=other),
        ).execute()
        assert not result.success
        assert "not a triage proposal" in (result.error or "")

    def test_promote_failure_propagates(self, tmp_path: Path) -> None:
        triage_dir = tmp_path / "Business" / "_triage"
        proposal = _write_proposal(triage_dir, "x.pdf.proposed.yml", approved=True)
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = CommandResult(success=False, error="promote failed: sibling pdf not found")
        with patch("bim.commands.doc.promote.promote.CommandPromote", return_value=cmd_mock):
            result = CommandTriageApprove(
                services=self._services(),
                params=TriageApproveParams(proposed_yml_path=proposal),
            ).execute()
        assert not result.success
        assert "promote failed" in (result.error or "")

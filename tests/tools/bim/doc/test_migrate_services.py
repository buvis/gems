"""Tests for ``get_migrate_services`` — Copilot round 1 findings 5 & 6.

- Finding 5: an audit that fails (no ``report``) must propagate as an error,
  not silently yield an empty migration plan.
- Finding 6: building migrate services must NOT persist a JSON report to
  ``<state_dir>/audit/`` (the audit is run with ``write_report=False``), so a
  dry-run plan leaves the state dir untouched.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings
from bim.dependencies import get_migrate_services
from buvis.pybase.result import CommandResult


def _doc_settings(tmp_path: Path) -> DocSettings:
    return DocSettings(
        paths=DocPaths.model_validate(
            {
                "business_root": str(tmp_path / "Business"),
                "vault_root": str(tmp_path / "Vault"),
                "state_dir": str(tmp_path / "state"),
                "issuers_file": str(tmp_path / "issuers.yml"),
            }
        ),
    )


class TestGetMigrateServicesFailurePropagation:
    def test_audit_failure_raises_runtimeerror(self, tmp_path: Path) -> None:
        settings = _doc_settings(tmp_path)
        failing = MagicMock()
        failing.execute.return_value = CommandResult(success=False, error="audit failed: io error")
        with (
            patch("bim.dependencies.get_audit_services", return_value=MagicMock()),
            patch("bim.commands.doc.audit.audit.CommandAudit", return_value=failing),
            pytest.raises(RuntimeError, match="audit failed"),
        ):
            get_migrate_services(settings)

    def test_missing_report_raises_runtimeerror(self, tmp_path: Path) -> None:
        settings = _doc_settings(tmp_path)
        no_report = MagicMock()
        no_report.execute.return_value = CommandResult(success=True, metadata={})
        with (
            patch("bim.dependencies.get_audit_services", return_value=MagicMock()),
            patch("bim.commands.doc.audit.audit.CommandAudit", return_value=no_report),
            pytest.raises(RuntimeError),
        ):
            get_migrate_services(settings)


class TestGetMigrateServicesNoWrite:
    def test_planning_runs_audit_with_write_report_false(self, tmp_path: Path) -> None:
        settings = _doc_settings(tmp_path)
        report = MagicMock()
        report.legacy_layout_zettels = ("/x.md",)
        cmd = MagicMock()
        cmd.execute.return_value = CommandResult(success=True, metadata={"report": report})
        with (
            patch("bim.dependencies.get_audit_services", return_value=MagicMock()),
            patch("bim.commands.doc.audit.audit.CommandAudit", return_value=cmd),
        ):
            services = get_migrate_services(settings)

        # the audit must be invoked read-only (no JSON report persisted)
        cmd.execute.assert_called_once_with(write_report=False)
        assert services.legacy_zettels == ("/x.md",)


class TestCommandAuditWriteReportSeam:
    """The shared audit gains a write_report seam (finding 6): write_report=False
    runs the audit read-only — no JSON report file is created under state_dir."""

    def test_write_report_false_writes_nothing(self, tmp_path: Path) -> None:
        from bim.commands.doc.audit.audit import AuditServices, CommandAudit

        business_root = tmp_path / "Business"
        vault_root = tmp_path / "Vault"
        business_root.mkdir()
        vault_root.mkdir()
        issuers = tmp_path / "issuers.yml"
        issuers.write_text("doc_types:\n- invoice\nissuers: {}\n", encoding="utf-8")
        state_dir = tmp_path / "state"

        class _Dedup:
            is_duplicate = True

        class _StubStateDB:
            def get_rule_last_matches(self) -> dict[str, object]:
                return {}

            def dedup(self, _sha: str) -> _Dedup:
                return _Dedup()

        services = AuditServices(
            state_db=_StubStateDB(),  # type: ignore[arg-type]
            business_root=business_root,
            vault_root=vault_root,
            vault_documents_subdir="Zettelkasten/documents",
            issuers_path=issuers,
            state_dir=state_dir,
            low_confidence_threshold=0.7,
            ocr_quality_reader=lambda _p: (True, None),
            hash_reader=lambda _p: "0" * 64,
        )

        result = CommandAudit(services=services).execute(write_report=False)

        assert result.success
        assert result.metadata["report_path"] is None
        # nothing written under state_dir/audit
        assert not (state_dir / "audit").exists()

    def test_write_report_true_persists_report(self, tmp_path: Path) -> None:
        from bim.commands.doc.audit.audit import AuditServices, CommandAudit

        business_root = tmp_path / "Business"
        vault_root = tmp_path / "Vault"
        business_root.mkdir()
        vault_root.mkdir()
        issuers = tmp_path / "issuers.yml"
        issuers.write_text("doc_types:\n- invoice\nissuers: {}\n", encoding="utf-8")
        state_dir = tmp_path / "state"

        class _Dedup:
            is_duplicate = True

        class _StubStateDB:
            def get_rule_last_matches(self) -> dict[str, object]:
                return {}

            def dedup(self, _sha: str) -> _Dedup:
                return _Dedup()

        services = AuditServices(
            state_db=_StubStateDB(),  # type: ignore[arg-type]
            business_root=business_root,
            vault_root=vault_root,
            vault_documents_subdir="Zettelkasten/documents",
            issuers_path=issuers,
            state_dir=state_dir,
            low_confidence_threshold=0.7,
            ocr_quality_reader=lambda _p: (True, None),
            hash_reader=lambda _p: "0" * 64,
        )

        result = CommandAudit(services=services).execute()  # default write_report=True

        assert result.success
        assert result.metadata["report_path"] is not None
        assert list((state_dir / "audit").glob("*.json"))

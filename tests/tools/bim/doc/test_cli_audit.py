"""CLI tests for ``bim doc audit``.

Mirrors the patching style used by ``test_cli_ingest`` / ``test_cli_promote``:
``get_settings`` is patched so the CLI receives a fully-formed ``BimSettings``
without needing a config file on disk, and the doc-subsystem factories are
patched to keep tests off the network and off pdfminer.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import cli
from bim.commands.doc.audit.models import AuditReport
from bim.commands.doc.shared.health import MissingDependency
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings
from bim.settings import BimSettings
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


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


def _bim_settings_with_doc(tmp_path: Path) -> BimSettings:
    return BimSettings(
        path_zettelkasten=str(tmp_path / "zk"),
        path_archive=str(tmp_path / "archive"),
        doc=_doc_settings(tmp_path),
    )


def _bim_settings_without_doc(tmp_path: Path) -> BimSettings:
    return BimSettings(
        path_zettelkasten=str(tmp_path / "zk"),
        path_archive=str(tmp_path / "archive"),
    )


def _empty_report() -> AuditReport:
    return AuditReport(
        walked_pdf_count=0,
        clean_pdf_count=0,
        pdf_findings=(),
        legacy_layout_zettels=(),
        rule_findings=(),
        issuer_inboxes=(),
        triage_pending=0,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        n_issuers_walked=0,
    )


def _legacy_report() -> AuditReport:
    """One PDF walked, found at the v0 (legacy) flat path so it is reported
    in ``legacy_layout_zettels`` and counts as non-clean (needs migration).
    """
    return AuditReport(
        walked_pdf_count=1,
        clean_pdf_count=0,
        non_clean_pdf_count=1,
        pdf_findings=(),
        legacy_layout_zettels=("/Vault/legacy.md",),
        rule_findings=(),
        issuer_inboxes=(),
        triage_pending=0,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        n_issuers_walked=1,
    )


def _patches_for_audit(settings: BimSettings, services_mock: MagicMock) -> list:
    """Patch every doc-subsystem factory the audit handler resolves."""
    return [
        patch("bim.doc_cli.get_settings", return_value=settings),
        patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
        patch("bim.dependencies.get_audit_services", return_value=services_mock),
    ]


class TestBimDocAuditHelp:
    def test_doc_audit_help_lists_command(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doc", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "audit" in result.output
        assert "Read-only audit" in result.output


class TestBimDocAudit:
    def test_doc_audit_runs_against_fixture(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        report_path = tmp_path / "state" / "audit" / "2026-01-01.json"
        cmd_result = CommandResult(
            success=True,
            metadata={
                "report": _empty_report(),
                "report_path": str(report_path),
                "walked_pdf_count": 0,
                "clean_pdf_count": 0,
                "legacy_layout_count": 0,
                "validation_errors": [],
            },
        )
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = cmd_result

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_audit(settings, MagicMock()):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.audit.audit.CommandAudit", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Audit complete." in result.output
        # The Rich console may line-wrap long paths in success output, including
        # inside the filename itself (e.g. splitting "2026-" from "01-01.json"
        # on the hyphen); strip newlines before checking so the test tolerates
        # any wrap point, not just wraps between path segments.
        assert "Report:" in result.output
        assert report_path.name in result.output.replace("\n", "")

    def test_doc_audit_writes_json_report(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        # The handler delegates writing to ``CommandAudit`` (which calls
        # ``write_json_report``). To assert the contract end-to-end we
        # simulate the side effect inside the mocked ``execute`` so the
        # test verifies the success path exposes the resulting path.
        state_dir = tmp_path / "state"
        report_dir = state_dir / "audit"

        def _execute_writes_json() -> CommandResult:
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "2026-01-01T00_00_00_00_00.json"
            report_path.write_text("{}", encoding="utf-8")
            return CommandResult(
                success=True,
                metadata={
                    "report": _empty_report(),
                    "report_path": str(report_path),
                    "walked_pdf_count": 0,
                    "clean_pdf_count": 0,
                    "legacy_layout_count": 0,
                    "validation_errors": [],
                },
            )

        cmd_mock = MagicMock()
        cmd_mock.execute.side_effect = _execute_writes_json

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_audit(settings, MagicMock()):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.audit.audit.CommandAudit", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=False)

        assert result.exit_code == 0
        json_files = list(report_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_doc_audit_renders_legacy_layout_count(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        cmd_result = CommandResult(
            success=True,
            metadata={
                "report": _legacy_report(),
                "report_path": "/tmp/report.json",
                "walked_pdf_count": 1,
                "clean_pdf_count": 1,
                "legacy_layout_count": 1,
                "validation_errors": [],
            },
        )
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = cmd_result

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_audit(settings, MagicMock()):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.audit.audit.CommandAudit", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "1 legacy layout zettels" in result.output

    def test_doc_audit_panics_when_doc_section_missing(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_without_doc(tmp_path)

        with patch("bim.doc_cli.get_settings", return_value=settings):
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=True)

        assert result.exit_code != 0 or "[doc] section missing" in result.output

    def test_doc_audit_missing_dependency_panics(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)

        def _raise(_s: object) -> None:
            raise MissingDependency("ocrmypdf not found")

        with (
            patch("bim.doc_cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=_raise),
        ):
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=True)

        assert result.exit_code != 0 or "ocrmypdf" in result.output

    def test_doc_audit_failure_prints_error(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        cmd_result = CommandResult(success=False, error="audit failed: io error")
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = cmd_result

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_audit(settings, MagicMock()):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.audit.audit.CommandAudit", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=False)

        assert "audit failed: io error" in result.output

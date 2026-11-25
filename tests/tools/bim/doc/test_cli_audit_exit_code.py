"""Exit-code contract for ``bim doc audit``'s terminal ``console.report_result``
call. Mirrors the patching style used by ``test_cli_audit.py``.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import cli
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


def _patches_for_audit(settings: BimSettings) -> list:
    return [
        patch("bim.doc_cli.get_settings", return_value=settings),
        patch("bim.dependencies.get_health_checker", return_value=lambda _s, _llm: None),
        patch("bim.dependencies.get_audit_services", return_value=MagicMock()),
    ]


class TestDocAuditExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = CommandResult(success=False, error="audit failed: io error")

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_audit(settings):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.audit.audit.CommandAudit", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=False)

        assert result.exit_code != 0
        assert "audit failed: io error" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        report_path = tmp_path / "state" / "audit" / "2026-01-01.json"
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = CommandResult(
            success=True,
            metadata={
                "report": MagicMock(legacy_layout_zettels=()),
                "report_path": str(report_path),
                "walked_pdf_count": 0,
                "clean_pdf_count": 0,
                "legacy_layout_count": 0,
                "validation_errors": [],
            },
        )

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_audit(settings):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.audit.audit.CommandAudit", return_value=cmd_mock))
            stack.enter_context(patch("bim.commands.doc.audit.reporter.render_stdout"))
            result = runner.invoke(cli, ["doc", "audit"], catch_exceptions=False)

        assert result.exit_code == 0

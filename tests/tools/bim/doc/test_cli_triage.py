"""CLI tests for ``bim doc triage`` (PRD 00057)."""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import cli
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings
from bim.settings import BimSettings
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


def _bim_settings_with_doc(tmp_path: Path) -> BimSettings:
    return BimSettings(
        path_zettelkasten=str(tmp_path / "zk"),
        path_archive=str(tmp_path / "archive"),
        doc=DocSettings(
            paths=DocPaths.model_validate(
                {
                    "business_root": str(tmp_path / "Business"),
                    "vault_root": str(tmp_path / "Vault"),
                    "state_dir": str(tmp_path / "state"),
                    "issuers_file": str(tmp_path / "issuers.yml"),
                }
            ),
        ),
    )


class TestBimDocTriageHelp:
    def test_help_lists_command(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doc", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "triage" in result.output

    def test_command_help_shows_approve(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["doc", "triage", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "--approve" in result.output


class TestBimDocTriageList:
    def test_list_runs_and_prints_output(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = CommandResult(
            success=True, output="1 pending triage proposal(s)", info=["/x.proposed.yml — cez-as/invoice"]
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("bim.doc_cli.get_settings", return_value=settings))
            stack.enter_context(patch("bim.dependencies.get_health_checker", return_value=lambda _s: None))
            stack.enter_context(patch("bim.dependencies.get_triage_list_services", return_value=MagicMock()))
            stack.enter_context(patch("bim.commands.doc.triage.triage.CommandTriageList", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "triage"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "1 pending" in result.output


class TestBimDocTriageApprove:
    def test_approve_resolves_id_and_promotes(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = CommandResult(
            success=True,
            metadata={"pdf_path": "/p.pdf", "zettel_path": "/z.md"},
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("bim.doc_cli.get_settings", return_value=settings))
            stack.enter_context(patch("bim.dependencies.get_health_checker", return_value=lambda _s: None))
            stack.enter_context(patch("bim.dependencies.get_triage_approve_services", return_value=MagicMock()))
            stack.enter_context(patch("bim.dependencies.get_repo", return_value=MagicMock()))
            approve_cls = stack.enter_context(
                patch("bim.commands.doc.triage.triage.CommandTriageApprove", return_value=cmd_mock)
            )
            result = runner.invoke(cli, ["doc", "triage", "--approve", "x.invoice"], catch_exceptions=False)

        assert result.exit_code == 0
        # the id "x.invoice" resolves to <business_root>/_triage/x.invoice.proposed.yml
        _, kwargs = approve_cls.call_args
        resolved = kwargs["params"].proposed_yml_path
        assert resolved == tmp_path / "Business" / "_triage" / "x.invoice.proposed.yml"

    def test_approve_failure_prints_error(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = CommandResult(success=False, error="approved must be true")
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("bim.doc_cli.get_settings", return_value=settings))
            stack.enter_context(patch("bim.dependencies.get_health_checker", return_value=lambda _s: None))
            stack.enter_context(patch("bim.dependencies.get_triage_approve_services", return_value=MagicMock()))
            stack.enter_context(patch("bim.dependencies.get_repo", return_value=MagicMock()))
            stack.enter_context(patch("bim.commands.doc.triage.triage.CommandTriageApprove", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "triage", "--approve", "x.invoice"], catch_exceptions=False)

        assert "approved must be true" in result.output

    def test_panics_when_doc_section_missing(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = BimSettings(
            path_zettelkasten=str(tmp_path / "zk"),
            path_archive=str(tmp_path / "archive"),
        )
        with patch("bim.doc_cli.get_settings", return_value=settings):
            result = runner.invoke(cli, ["doc", "triage"], catch_exceptions=True)
        assert result.exit_code != 0 or "[doc] section missing" in result.output

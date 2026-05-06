from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import cli
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
            }
        ),
    )


def _bim_settings_with_doc(tmp_path: Path) -> BimSettings:
    return BimSettings(
        path_zettelkasten=str(tmp_path / "zk"),
        path_archive=str(tmp_path / "archive"),
        doc=_doc_settings(tmp_path),
    )


def _staged_yml(tmp_path: Path) -> Path:
    yml = tmp_path / "x.proposed.yml"
    yml.write_text("approved: true\n", encoding="utf-8")
    return yml


def _patches_for_promote(settings: BimSettings) -> list:
    """Patch every doc-subsystem factory that the promote handler resolves."""
    return [
        patch("bim.cli.get_settings", return_value=settings),
        patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
        patch(
            "bim.dependencies.get_issuer_registry",
            return_value=(MagicMock(), Path("/tmp/i.yml"), Path("/tmp/i.lock")),
        ),
        patch("bim.dependencies.get_state_db", return_value=MagicMock()),
        patch("bim.dependencies.get_ocr_runner", return_value=MagicMock()),
        patch("bim.dependencies.get_zettel_writer", return_value=MagicMock()),
        patch("bim.dependencies.get_repo", return_value=MagicMock()),
    ]


class TestBimDocPromote:
    def test_happy_path_prints_success(self, runner: CliRunner, tmp_path: Path) -> None:
        yml = _staged_yml(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)
        target_pdf = tmp_path / "Business" / "cez-as" / "x.invoice.pdf"
        zettel_path = tmp_path / "Vault" / "Zettelkasten" / "documents" / "x.invoice.md"
        cmd_result = CommandResult(
            success=True,
            metadata={
                "pdf_path": str(target_pdf),
                "zettel_path": str(zettel_path),
                "canonical_filename": "x.invoice.pdf",
            },
        )
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = cmd_result

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_promote(settings):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.promote.promote.CommandPromote", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "promote", str(yml)], catch_exceptions=False)

        assert result.exit_code == 0
        assert "promoted" in result.output

    def test_validation_failure_prints_error(self, runner: CliRunner, tmp_path: Path) -> None:
        yml = _staged_yml(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)
        cmd_result = CommandResult(success=False, error="approved must be true")
        cmd_mock = MagicMock()
        cmd_mock.execute.return_value = cmd_result

        with contextlib.ExitStack() as stack:
            for ctx in _patches_for_promote(settings):
                stack.enter_context(ctx)
            stack.enter_context(patch("bim.commands.doc.promote.promote.CommandPromote", return_value=cmd_mock))
            result = runner.invoke(cli, ["doc", "promote", str(yml)], catch_exceptions=False)

        assert "approved must be true" in result.output

    def test_missing_dependency_panics(self, runner: CliRunner, tmp_path: Path) -> None:
        yml = _staged_yml(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)

        def _raise(_s: object) -> None:
            raise MissingDependency("ollama not reachable")

        with (
            patch("bim.cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=_raise),
        ):
            result = runner.invoke(cli, ["doc", "promote", str(yml)], catch_exceptions=True)

        assert result.exit_code != 0 or "ollama" in result.output

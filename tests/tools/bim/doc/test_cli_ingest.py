from __future__ import annotations

import subprocess
import sys
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


def _staged_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfake\n")
    return pdf


class TestBimDocIngest:
    def test_filed_outcome_prints_success(self, runner: CliRunner, tmp_path: Path) -> None:
        pdf = _staged_pdf(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)
        target_pdf = tmp_path / "Business" / "cez-as" / "20210311083422-cez-as-x.invoice.pdf"
        zettel_path = tmp_path / "Vault" / "Zettelkasten" / "documents" / "20210311083422-cez-as-x.invoice.md"
        cmd_result = CommandResult(
            success=True,
            metadata={
                "outcome": "filed",
                "pdf_path": str(target_pdf),
                "zettel_path": str(zettel_path),
            },
        )
        pipeline_mock = MagicMock()
        pipeline_mock.run.return_value = cmd_result

        with (
            patch("bim.cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
            patch("bim.dependencies.get_pipeline", return_value=pipeline_mock),
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["doc", "ingest", str(pdf)], catch_exceptions=False)

        assert result.exit_code == 0
        assert "filed" in result.output

    def test_triaged_outcome_prints_warning(self, runner: CliRunner, tmp_path: Path) -> None:
        pdf = _staged_pdf(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)
        proposal_path = tmp_path / "Business" / "_triage" / "x.proposed.yml"
        cmd_result = CommandResult(
            success=True,
            metadata={"outcome": "triaged", "proposal_path": str(proposal_path)},
        )
        pipeline_mock = MagicMock()
        pipeline_mock.run.return_value = cmd_result

        with (
            patch("bim.cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
            patch("bim.dependencies.get_pipeline", return_value=pipeline_mock),
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["doc", "ingest", str(pdf)], catch_exceptions=False)

        assert result.exit_code == 0
        assert "triaged" in result.output

    def test_duplicate_outcome_prints_warning(self, runner: CliRunner, tmp_path: Path) -> None:
        pdf = _staged_pdf(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)
        cmd_result = CommandResult(
            success=True,
            metadata={
                "outcome": "duplicate",
                "existing_canonical_filename": "20210311083422-cez-as-7102105594.invoice.pdf",
            },
        )
        pipeline_mock = MagicMock()
        pipeline_mock.run.return_value = cmd_result

        with (
            patch("bim.cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
            patch("bim.dependencies.get_pipeline", return_value=pipeline_mock),
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["doc", "ingest", str(pdf)], catch_exceptions=False)

        assert result.exit_code == 0
        assert "duplicate" in result.output

    def test_missing_dependency_panics(self, runner: CliRunner, tmp_path: Path) -> None:
        pdf = _staged_pdf(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)

        def _raise(_s: object) -> None:
            raise MissingDependency("ocrmypdf not found")

        with (
            patch("bim.cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=_raise),
        ):
            result = runner.invoke(cli, ["doc", "ingest", str(pdf)], catch_exceptions=True)

        # console.panic exits non-zero
        assert result.exit_code != 0 or "ocrmypdf" in result.output

    def test_issuer_flag_is_threaded_into_params(self, runner: CliRunner, tmp_path: Path) -> None:
        pdf = _staged_pdf(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)
        cmd_result = CommandResult(success=True, metadata={"outcome": "filed"})
        pipeline_mock = MagicMock()
        pipeline_mock.run.return_value = cmd_result

        captured: dict[str, object] = {}

        def _fake_command_ingest(*, params: object, pipeline: object) -> object:
            captured["params"] = params
            captured["pipeline"] = pipeline
            cmd = MagicMock()
            cmd.execute.return_value = cmd_result
            return cmd

        with (
            patch("bim.cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
            patch("bim.dependencies.get_pipeline", return_value=pipeline_mock),
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.commands.doc.ingest.ingest.CommandIngest", side_effect=_fake_command_ingest),
        ):
            result = runner.invoke(
                cli,
                ["doc", "ingest", "--issuer", "cez-as", "--source", "issuer-inbox", str(pdf)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        params = captured["params"]
        assert getattr(params, "issuer_slug_hint", None) == "cez-as"
        assert getattr(params, "source", None) == "issuer-inbox"


class TestLazyImportInvariant:
    """Ensure ``bim.dependencies`` doesn't pull in ocrmypdf/requests at import time."""

    def test_import_dependencies_does_not_load_optional_extras(self) -> None:
        # Reference the module after import so static analysers don't flag F401.
        code = (
            "import sys\n"
            "import bim.dependencies\n"
            "assert bim.dependencies.__name__ == 'bim.dependencies'\n"
            "leaked = [m for m in ('requests', 'ocrmypdf', 'pdfminer') if m in sys.modules]\n"
            "assert leaked == [], f'lazy-import drift: {leaked} loaded by bim.dependencies'\n"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, check=False)
        assert result.returncode == 0, result.stderr.decode(errors="replace")


class TestBimDocIngestStrictFlag:
    """`--strict` maps success=False to exit 1 instead of exit 0."""

    def _run(self, runner: CliRunner, tmp_path: Path, cmd_result: CommandResult, *args: str) -> object:
        pdf = _staged_pdf(tmp_path)
        settings = _bim_settings_with_doc(tmp_path)
        pipeline_mock = MagicMock()
        pipeline_mock.run.return_value = cmd_result
        with (
            patch("bim.cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_health_checker", return_value=lambda _s: None),
            patch("bim.dependencies.get_pipeline", return_value=pipeline_mock),
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            return runner.invoke(cli, ["doc", "ingest", str(pdf), *args])

    def test_default_exits_zero_on_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        cmd_result = CommandResult(success=False, error="pipeline failed: oops")
        result = self._run(runner, tmp_path, cmd_result)
        assert result.exit_code == 0

    def test_strict_exits_one_on_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        cmd_result = CommandResult(success=False, error="pipeline failed: oops")
        result = self._run(runner, tmp_path, cmd_result, "--strict")
        assert result.exit_code == 1

    def test_strict_exits_zero_on_triaged(self, runner: CliRunner, tmp_path: Path) -> None:
        cmd_result = CommandResult(
            success=True,
            metadata={"outcome": "triaged", "proposal_path": "/tmp/x.proposed.yml"},
        )
        result = self._run(runner, tmp_path, cmd_result, "--strict")
        assert result.exit_code == 0

    def test_strict_exits_zero_on_duplicate(self, runner: CliRunner, tmp_path: Path) -> None:
        cmd_result = CommandResult(
            success=True,
            metadata={"outcome": "duplicate", "existing_canonical_filename": "x.pdf"},
        )
        result = self._run(runner, tmp_path, cmd_result, "--strict")
        assert result.exit_code == 0

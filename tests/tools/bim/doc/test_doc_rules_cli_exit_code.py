"""Exit-code contract for ``bim doc rules``'s terminal ``console.report_result``
calls: ``list`` (~line 43) and ``backtest`` (~line 151). ``validate`` and
``test`` are out of scope: their failure paths call ``console.panic``
directly, never ``console.report_result``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from bim.cli import cli
from bim.commands.doc.shared.settings_models import DocPaths, DocSettings
from bim.settings import BimSettings
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


def _bim_settings_with_doc(tmp_path: Path) -> BimSettings:
    doc_settings = DocSettings(
        paths=DocPaths.model_validate(
            {
                "business_root": str(tmp_path / "Business"),
                "vault_root": str(tmp_path / "Vault"),
                "state_dir": str(tmp_path / "state"),
                "issuers_file": str(tmp_path / "issuers.yml"),
            }
        ),
    )
    return BimSettings(
        path_zettelkasten=str(tmp_path / "zk"),
        path_archive=str(tmp_path / "archive"),
        doc=doc_settings,
    )


class TestDocRulesListExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        fake_result = CommandResult(success=False, error="list failed: malformed issuers.yml")

        with (
            patch("bim.doc_rules_cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_issuer_registry", return_value=MagicMock(registry=MagicMock())),
            patch(
                "bim.commands.doc.rules.list.CommandRulesList",
                return_value=SimpleNamespace(run=lambda *_a, **_k: fake_result),
            ),
        ):
            result = runner.invoke(cli, ["doc", "rules", "list"], catch_exceptions=False)

        assert result.exit_code != 0
        assert "list failed: malformed issuers.yml" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        fake_result = CommandResult(success=True, output="cez-as: 2 rules\neon-cz: 1 rule")

        with (
            patch("bim.doc_rules_cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_issuer_registry", return_value=MagicMock(registry=MagicMock())),
            patch(
                "bim.commands.doc.rules.list.CommandRulesList",
                return_value=SimpleNamespace(run=lambda *_a, **_k: fake_result),
            ),
        ):
            result = runner.invoke(cli, ["doc", "rules", "list"], catch_exceptions=False)

        assert result.exit_code == 0


class TestDocRulesBacktestExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        fake_result = CommandResult(success=False, error="backtest failed: unreadable archive")

        with (
            patch("bim.doc_rules_cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_issuer_registry", return_value=MagicMock(registry=MagicMock())),
            patch("bim.dependencies.get_ocr_runner", return_value=MagicMock()),
            patch(
                "bim.commands.doc.rules.backtest.CommandRulesBacktest",
                return_value=SimpleNamespace(run=lambda *_a, **_k: fake_result),
            ),
        ):
            result = runner.invoke(cli, ["doc", "rules", "backtest"], catch_exceptions=False)

        assert result.exit_code != 0
        assert "backtest failed: unreadable archive" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        fake_result = CommandResult(success=True, output="cez-fingerprint: 3 matches")

        with (
            patch("bim.doc_rules_cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_issuer_registry", return_value=MagicMock(registry=MagicMock())),
            patch("bim.dependencies.get_ocr_runner", return_value=MagicMock()),
            patch(
                "bim.commands.doc.rules.backtest.CommandRulesBacktest",
                return_value=SimpleNamespace(run=lambda *_a, **_k: fake_result),
            ),
        ):
            result = runner.invoke(cli, ["doc", "rules", "backtest"], catch_exceptions=False)

        assert result.exit_code == 0


class TestUnusableIssuersFile:
    """A missing, malformed or empty issuers.yml is a console error, never a traceback."""

    @pytest.mark.parametrize("command", [["list"], ["backtest"]])
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            (None, "issuers file not found"),
            ("issuers: [unclosed", "cannot load issuers file"),
            ("", "cannot load issuers file"),
            ("version: 1\nissuers: {acme: 5}\n", "cannot load issuers file"),
            ("issuers: {}\n", "cannot load issuers file"),
        ],
        ids=["missing", "malformed", "empty", "wrong-shape", "no-version"],
    )
    def test_rules_command_reports_it_through_the_console(
        self, runner: CliRunner, tmp_path: Path, command: list[str], content: str | None, expected: str
    ) -> None:
        settings = _bim_settings_with_doc(tmp_path)
        if content is not None:
            (tmp_path / "issuers.yml").write_text(content)

        with (
            patch("bim.doc_rules_cli.get_settings", return_value=settings),
            patch("bim.dependencies.get_ocr_runner", return_value=MagicMock()),
        ):
            result = runner.invoke(cli, ["doc", "rules", *command])

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert expected in result.output
        assert "issuers.yml" in result.output.replace("\n", "")

    def test_missing_doc_section_message_names_the_section(self, runner: CliRunner, tmp_path: Path) -> None:
        settings = BimSettings(path_zettelkasten=str(tmp_path / "zk"), path_archive=str(tmp_path / "archive"))

        with patch("bim.doc_rules_cli.get_settings", return_value=settings):
            result = runner.invoke(cli, ["doc", "rules", "list"])

        assert result.exit_code == 1
        assert "`doc` section missing in bim config" in result.output

"""Exit-code contract for ``bim doc rules``'s terminal ``console.report_result``
calls: ``list`` (~line 43) and ``backtest`` (~line 151). ``validate`` and
``test`` are out of scope: their failure paths call ``console.panic``
directly, never ``console.report_result``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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

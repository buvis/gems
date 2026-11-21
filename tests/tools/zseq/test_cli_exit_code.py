from __future__ import annotations

from types import SimpleNamespace

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from zseq.cli import cli


class TestGetLastExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path):
        fake_result = CommandResult(success=False, error="no sequenced files found")
        mocker.patch(
            "zseq.commands.get_last.get_last.CommandGetLast",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["-p", str(tmp_path)])

        assert result.exit_code != 0
        assert "no sequenced files found" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path):
        fake_result = CommandResult(success=True, output="20260101120000")
        mocker.patch(
            "zseq.commands.get_last.get_last.CommandGetLast",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["-p", str(tmp_path)])

        assert result.exit_code == 0

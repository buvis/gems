from __future__ import annotations

from types import SimpleNamespace

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from dot.cli import cli


class TestStatusExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker):
        fake_result = CommandResult(
            success=False,
            error="Error hiding secrets: gpg key missing",
        )
        mocker.patch(
            "dot.commands.status.status.CommandStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["status"])

        assert result.exit_code != 0
        assert "Error hiding secrets: gpg key missing" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker):
        fake_result = CommandResult(success=True)
        mocker.patch(
            "dot.commands.status.status.CommandStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["status"])

        assert result.exit_code == 0

    def test_exits_nonzero_with_falsy_error_message(self, mocker):
        # A failing result with an empty error string must still exit
        # non-zero: the exit decision must key off `success`, not the
        # truthiness of `error`.
        fake_result = CommandResult(success=False, error="")
        mocker.patch(
            "dot.commands.status.status.CommandStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["status"])

        assert result.exit_code != 0

    def test_exits_zero_despite_truthy_error_field_when_result_succeeds(self, mocker):
        # A successful result that happens to carry a non-empty `error`
        # field (e.g. a stale value) must still exit zero: the exit
        # decision must key off `success`, not the truthiness of `error`.
        fake_result = CommandResult(success=True, error="stale warning text")
        mocker.patch(
            "dot.commands.status.status.CommandStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["status"])

        assert result.exit_code == 0

    def test_failure_output_includes_details_from_metadata(self, mocker):
        fake_result = CommandResult(
            success=False,
            error="Error hiding secrets: boom",
            metadata={"details": "file.txt: permission denied"},
        )
        mocker.patch(
            "dot.commands.status.status.CommandStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["status"])

        assert result.exit_code != 0
        assert "file.txt: permission denied" in result.output

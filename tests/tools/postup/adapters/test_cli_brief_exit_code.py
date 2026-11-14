from __future__ import annotations

from types import SimpleNamespace

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from postup.adapters.cli import cli


class TestBarePostupExitCode:
    def test_exits_nonzero_when_brief_result_fails(self, mocker, tmp_path, monkeypatch):
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(
            success=False,
            error="no data.json found; run postup collect first",
        )
        mocker.patch(
            "postup.commands.brief.brief.CommandBrief",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, [])

        assert result.exit_code != 0
        assert "no data.json found; run postup collect first" in result.output

    def test_exits_zero_when_brief_result_succeeds(self, mocker, tmp_path, monkeypatch):
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(
            success=True,
            metadata={"text": "standup: all quiet"},
        )
        mocker.patch(
            "postup.commands.brief.brief.CommandBrief",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, [])

        assert result.exit_code == 0
        assert "standup: all quiet" in result.output

    def test_exits_nonzero_with_falsy_error_message(self, mocker, tmp_path, monkeypatch):
        # A failing result with an empty error string must still exit
        # non-zero: the exit decision must key off `success`, not the
        # truthiness of `error`.
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=False, error="")
        mocker.patch(
            "postup.commands.brief.brief.CommandBrief",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, [])

        assert result.exit_code != 0

    def test_exits_zero_despite_truthy_error_field_when_result_succeeds(self, mocker, tmp_path, monkeypatch):
        # A successful result that happens to carry a non-empty `error`
        # field must still exit zero: the exit decision must key off
        # `success`, not the truthiness of `error`.
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=True, error="stale warning text")
        mocker.patch(
            "postup.commands.brief.brief.CommandBrief",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, [])

        assert result.exit_code == 0


class TestBriefSubcommandExitCode:
    def test_exits_nonzero_when_brief_result_fails(self, mocker, tmp_path, monkeypatch):
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(
            success=False,
            error="no data.json found; run postup collect first",
        )
        mocker.patch(
            "postup.commands.brief.brief.CommandBrief",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["brief"])

        assert result.exit_code != 0
        assert "no data.json found; run postup collect first" in result.output

    def test_exits_zero_when_brief_result_succeeds(self, mocker, tmp_path, monkeypatch):
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(
            success=True,
            metadata={"text": "standup: all quiet"},
        )
        mocker.patch(
            "postup.commands.brief.brief.CommandBrief",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["brief"])

        assert result.exit_code == 0
        assert "standup: all quiet" in result.output

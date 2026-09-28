"""``CommandServe`` and ``postup serve`` CLI-wiring tests."""

from __future__ import annotations

import builtins
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from postup.adapters.cli import cli
from postup.commands.serve.serve import MISSING_EXTRA_ERROR, CommandServe
from postup.params.serve import ServeParams
from postup.settings import PostupSettings


def _settings(tmp_path) -> PostupSettings:
    return PostupSettings(out_dir=str(tmp_path / "out"))


class TestCommandServeInit:
    def test_stores_settings_and_params(self, tmp_path) -> None:
        params = ServeParams(host="0.0.0.0", port=9001, no_browser=True)
        cmd = CommandServe(_settings(tmp_path), params)
        assert cmd.params.host == "0.0.0.0"
        assert cmd.params.port == 9001
        assert cmd.params.no_browser is True


class TestCommandServeMissingExtra:
    def test_missing_web_extra_returns_failure_sentinel_not_raise(self, tmp_path) -> None:
        real_import = builtins.__import__

        def _no_uvicorn(name: str, *args: object, **kwargs: object) -> object:
            if name == "uvicorn":
                raise ImportError("No module named 'uvicorn'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", _no_uvicorn):
            result = CommandServe(_settings(tmp_path), ServeParams()).execute()

        assert result.success is False
        assert result.error == MISSING_EXTRA_ERROR
        assert result.metadata["missing_extra"] == "postup-web"


class TestCommandServeExecute:
    def test_builds_app_with_host_and_runs_uvicorn(self, tmp_path) -> None:
        pytest.importorskip("uvicorn")
        params = ServeParams(host="127.0.0.1", port=9123, no_browser=True)
        settings = _settings(tmp_path)
        cmd = CommandServe(settings, params)

        with (
            patch("postup.adapters.web.create_app") as mock_create_app,
            patch("uvicorn.run") as mock_run,
        ):
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            result = cmd.execute()

        mock_create_app.assert_called_once_with(settings, host="127.0.0.1")
        mock_run.assert_called_once_with(mock_app, host="127.0.0.1", port=9123, log_level="info")
        assert result.success is True

    def test_no_browser_skips_webbrowser_open(self, tmp_path) -> None:
        pytest.importorskip("uvicorn")
        cmd = CommandServe(_settings(tmp_path), ServeParams(no_browser=True))
        with (
            patch("postup.adapters.web.create_app"),
            patch("uvicorn.run"),
            patch("webbrowser.open") as mock_open,
        ):
            cmd.execute()
        mock_open.assert_not_called()

    def test_bind_oserror_returns_failure_not_raise(self, tmp_path) -> None:
        pytest.importorskip("uvicorn")
        cmd = CommandServe(_settings(tmp_path), ServeParams(no_browser=True))
        with (
            patch("postup.adapters.web.create_app"),
            patch("uvicorn.run", side_effect=OSError("address already in use")),
        ):
            result = cmd.execute()
        assert result.success is False
        assert "failed to start server" in result.error


class TestServeCliWiring:
    def test_serve_missing_extra_routes_to_require_import(self, tmp_path) -> None:
        runner = CliRunner()
        fake_result = MagicMock()
        fake_result.success = False
        fake_result.error = MISSING_EXTRA_ERROR
        with (
            patch("postup.commands.serve.serve.CommandServe") as mock_cmd,
            patch("postup.adapters.cli.console.require_import") as mock_require,
        ):
            mock_cmd.return_value.execute.return_value = fake_result
            runner.invoke(cli, ["serve", "--no-browser"])
        mock_require.assert_called_once()
        assert mock_require.call_args.args[0] == "postup-web"

    def test_serve_passes_options_to_params(self, tmp_path) -> None:
        runner = CliRunner()
        ok = MagicMock()
        ok.success = True
        ok.error = None
        with (
            patch("postup.commands.serve.serve.CommandServe") as mock_cmd,
            patch("postup.params.serve.ServeParams") as mock_params,
            patch("postup.adapters.cli.console.report_result"),
        ):
            mock_cmd.return_value.execute.return_value = ok
            runner.invoke(cli, ["serve", "-H", "0.0.0.0", "-p", "9999", "--no-browser"])
        mock_params.assert_called_once_with(host="0.0.0.0", port=9999, no_browser=True)

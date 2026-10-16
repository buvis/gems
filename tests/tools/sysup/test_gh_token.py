from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from sysup.capabilities.gh_token import GhTokenExpiry, parse_expiration

_HEADER = "Github-Authentication-Token-Expiration: 2027-10-13 18:05:04 UTC"
_USER_STDOUT = f"HTTP/2.0 200 OK\n{_HEADER}\nX-Other: 1\n\n{{}}\n"


def _done(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestParseExpiration:
    def test_header_date_parses_utc_and_numeric_offset(self) -> None:
        expected = datetime(2027, 10, 13, 18, 5, 4, tzinfo=timezone.utc)
        assert parse_expiration("2027-10-13 18:05:04 UTC") == expected
        assert parse_expiration("2027-10-13 18:05:04 +0000") == expected
        assert parse_expiration("2027-10-13 20:05:04 +0200") == expected


class TestGhTokenExpiry:
    def test_missing_gh_reports_unknown(self, mocker) -> None:
        mocker.patch("sysup.capabilities.gh_token.shutil.which", return_value=None)
        run = mocker.patch("sysup.capabilities.gh_token.subprocess.run")
        result = GhTokenExpiry().expires_at(config_dir="~/.config/gh-agent", probe="repos/x/y")
        assert result == "gh not found"
        assert run.call_count == 0

    def test_missing_header_reports_unknown(self, mocker) -> None:
        mocker.patch("sysup.capabilities.gh_token.shutil.which", return_value="/usr/bin/gh")
        mocker.patch(
            "sysup.capabilities.gh_token.subprocess.run",
            return_value=_done(stdout="HTTP/2.0 200 OK\n\n{}\n"),
        )
        result = GhTokenExpiry().expires_at(config_dir="/cfg", probe="repos/x/y")
        assert result == "no Github-Authentication-Token-Expiration header (token without expiry?)"

    def test_probe_denied_reports_unknown_grant_broken(self, mocker) -> None:
        mocker.patch("sysup.capabilities.gh_token.shutil.which", return_value="/usr/bin/gh")
        mocker.patch(
            "sysup.capabilities.gh_token.subprocess.run",
            side_effect=[_done(stdout=_USER_STDOUT), _done(returncode=1, stderr="HTTP 404")],
        )
        result = GhTokenExpiry().expires_at(config_dir="/cfg", probe="repos/x/y")
        assert result == "grant broken: gh api repos/x/y: HTTP 404"

    def test_config_dir_is_passed_as_env_not_argv(self, mocker, tmp_path) -> None:
        mocker.patch("sysup.capabilities.gh_token.shutil.which", return_value="/usr/bin/gh")
        run = mocker.patch(
            "sysup.capabilities.gh_token.subprocess.run",
            side_effect=[_done(stdout=_USER_STDOUT), _done()],
        )
        cfg_dir = tmp_path / "gh-agent"
        result = GhTokenExpiry().expires_at(config_dir=str(cfg_dir), probe="repos/x/y")
        assert result == datetime(2027, 10, 13, 18, 5, 4, tzinfo=timezone.utc)
        for call in run.call_args_list:
            argv = call.args[0]
            assert str(cfg_dir) not in argv
            assert call.kwargs["env"]["GH_CONFIG_DIR"] == str(cfg_dir)

    def test_probe_ignores_ambient_auth_and_host(self, mocker, monkeypatch, tmp_path) -> None:
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
            monkeypatch.setenv(name, f"synthetic-{name}")
        mocker.patch("sysup.capabilities.gh_token.shutil.which", return_value="/usr/bin/gh")
        run = mocker.patch(
            "sysup.capabilities.gh_token.subprocess.run",
            side_effect=[_done(stdout=_USER_STDOUT), _done()],
        )
        cfg_dir = tmp_path / "gh-agent"
        result = GhTokenExpiry().expires_at(config_dir=str(cfg_dir), probe="repos/x/y")
        assert isinstance(result, datetime)
        assert run.call_count == 2
        for call in run.call_args_list:
            argv = call.args[0]
            env = call.kwargs["env"]
            assert argv[:4] == ["/usr/bin/gh", "api", "--hostname", "github.com"]
            for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
                assert name not in env
            assert env["GH_CONFIG_DIR"] == str(cfg_dir)
        import os

        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
            assert os.environ[name] == f"synthetic-{name}"

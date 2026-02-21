from __future__ import annotations

import subprocess

from sysup.commands.pip.pip import CommandPip


class TestCommandPip:
    @staticmethod
    def _result(
        args: list[str],
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)

    def test_all_packages_updated(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.sys.executable", "/mock/python")
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":"alpha"},{"name":"beta"}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "alpha"]),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "beta"]),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip" and s.success for s in steps)
        assert any(s.label == "alpha" and s.success for s in steps)
        assert any(s.label == "beta" and s.success for s in steps)

    def test_pip_upgrade_fails(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.sys.executable", "/mock/python")
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"], returncode=1, stderr="nope"),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout="[]",
            ),
        ]

        steps = CommandPip().execute()

        pip_step = next(s for s in steps if s.label == "pip")
        assert pip_step.success is False
        assert "nope" in pip_step.message
        # Still continues to check outdated
        assert len(steps) >= 2

    def test_no_outdated_packages(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.sys.executable", "/mock/python")
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout="[]",
            ),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip packages" and s.success and "no outdated" in s.message for s in steps)

    def test_outdated_check_fails(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.sys.executable", "/mock/python")
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                returncode=2,
                stderr="list failed",
            ),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip outdated" and not s.success for s in steps)
        assert mock_run.call_count == 2

    def test_individual_package_fails(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.sys.executable", "/mock/python")
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":"alpha"},{"name":"beta"}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "alpha"], returncode=1, stderr="bad"),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "beta"]),
        ]

        steps = CommandPip().execute()

        alpha = next(s for s in steps if s.label == "alpha")
        assert alpha.success is False
        assert "bad" in alpha.message
        assert any(s.label == "beta" and s.success for s in steps)

    def test_malformed_json(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.sys.executable", "/mock/python")
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout="not-json",
            ),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip outdated" and not s.success and "parse" in s.message for s in steps)

    def test_uses_sys_executable(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.sys.executable", "/mock/python")
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":"alpha"}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "alpha"]),
        ]

        CommandPip().execute()

        for call_item in mock_run.call_args_list:
            assert call_item.args[0][0] == "/mock/python"

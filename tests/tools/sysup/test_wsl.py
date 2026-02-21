from __future__ import annotations

import subprocess

import pytest
from buvis.pybase.result import FatalError

from sysup.commands.wsl.wsl import CommandWsl


class TestCommandWsl:
    @staticmethod
    def _result(args: list[str], returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr=stderr)

    def test_all_steps_succeed(self, mocker) -> None:
        mapping = {"apt": "/usr/bin/apt", "snap": "/usr/bin/snap"}
        mocker.patch("sysup.commands.wsl.wsl.shutil.which", side_effect=lambda name: mapping.get(name))
        mock_run = mocker.patch("sysup.commands.wsl.wsl.subprocess.run")
        mock_run.side_effect = [
            self._result(["sudo", "/usr/bin/apt", "update"]),
            self._result(["sudo", "/usr/bin/apt", "upgrade", "-y"]),
            self._result(["sudo", "/usr/bin/apt", "autoremove", "-y"]),
            self._result(["sudo", "/usr/bin/snap", "refresh"]),
        ]

        steps = CommandWsl().execute()

        assert len(steps) == 4
        assert all(s.success for s in steps)
        labels = [s.label for s in steps]
        assert "apt update" in labels
        assert "apt upgrade" in labels
        assert "apt autoremove" in labels
        assert "snap" in labels

    def test_apt_missing_raises(self, mocker) -> None:
        mocker.patch("sysup.commands.wsl.wsl.shutil.which", return_value=None)

        with pytest.raises(FatalError, match="apt not found"):
            CommandWsl().execute()

    def test_snap_missing_skips(self, mocker) -> None:
        mapping = {"apt": "/usr/bin/apt", "snap": None}
        mocker.patch("sysup.commands.wsl.wsl.shutil.which", side_effect=lambda name: mapping.get(name))
        mock_run = mocker.patch("sysup.commands.wsl.wsl.subprocess.run")
        mock_run.side_effect = [
            self._result(["sudo", "/usr/bin/apt", "update"]),
            self._result(["sudo", "/usr/bin/apt", "upgrade", "-y"]),
            self._result(["sudo", "/usr/bin/apt", "autoremove", "-y"]),
        ]

        steps = CommandWsl().execute()

        assert mock_run.call_count == 3
        snap_step = next(s for s in steps if s.label == "snap")
        assert snap_step.success is False
        assert "not found" in snap_step.message

    def test_apt_step_fails_continues(self, mocker) -> None:
        mapping = {"apt": "/usr/bin/apt", "snap": "/usr/bin/snap"}
        mocker.patch("sysup.commands.wsl.wsl.shutil.which", side_effect=lambda name: mapping.get(name))
        mock_run = mocker.patch("sysup.commands.wsl.wsl.subprocess.run")
        mock_run.side_effect = [
            self._result(["sudo", "/usr/bin/apt", "update"], returncode=1, stderr="update failed"),
            self._result(["sudo", "/usr/bin/apt", "upgrade", "-y"]),
            self._result(["sudo", "/usr/bin/apt", "autoremove", "-y"]),
            self._result(["sudo", "/usr/bin/snap", "refresh"]),
        ]

        steps = CommandWsl().execute()

        apt_update = next(s for s in steps if s.label == "apt update")
        assert apt_update.success is False
        assert "update failed" in apt_update.message
        assert mock_run.call_count == 4

    def test_snap_fails(self, mocker) -> None:
        mapping = {"apt": "/usr/bin/apt", "snap": "/usr/bin/snap"}
        mocker.patch("sysup.commands.wsl.wsl.shutil.which", side_effect=lambda name: mapping.get(name))
        mock_run = mocker.patch("sysup.commands.wsl.wsl.subprocess.run")
        mock_run.side_effect = [
            self._result(["sudo", "/usr/bin/apt", "update"]),
            self._result(["sudo", "/usr/bin/apt", "upgrade", "-y"]),
            self._result(["sudo", "/usr/bin/apt", "autoremove", "-y"]),
            self._result(["sudo", "/usr/bin/snap", "refresh"], returncode=1, stderr="snap broken"),
        ]

        steps = CommandWsl().execute()

        snap_step = next(s for s in steps if s.label == "snap")
        assert snap_step.success is False
        assert "snap broken" in snap_step.message

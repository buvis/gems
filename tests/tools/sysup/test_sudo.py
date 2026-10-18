from __future__ import annotations

import subprocess

from sysup.capabilities.sudo import SudoPrime


class TestSudoPrime:
    @staticmethod
    def _result(returncode: int = 0) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["sudo", "-v"], returncode=returncode)

    def test_primes_and_returns_stop_callback(self, mocker) -> None:
        mocker.patch("sysup.capabilities.sudo.shutil.which", return_value="/usr/bin/sudo")
        mock_run = mocker.patch("sysup.capabilities.sudo.subprocess.run", return_value=self._result())
        thread = mocker.patch("sysup.capabilities.sudo.threading.Thread")

        stop = SudoPrime().prime()

        assert mock_run.call_args_list[0].args[0] == [
            "/usr/bin/sudo",
            "-p",
            "sysup needs your password: ",
            "-v",
        ]
        assert thread.called
        # stop callback is the Event.set method; calling it must not raise.
        stop()

    def test_banner_printed_before_prime_spawn(self, mocker) -> None:
        mocker.patch("sysup.capabilities.sudo.shutil.which", return_value="/usr/bin/sudo")
        mocker.patch("sysup.capabilities.sudo.threading.Thread")
        calls: list[str] = []

        def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append("run")
            return self._result()

        def fake_info(*args: object, **kwargs: object) -> None:
            calls.append("info")

        mocker.patch("sysup.capabilities.sudo.subprocess.run", side_effect=fake_run)
        mock_info = mocker.patch("sysup.capabilities.sudo.console.info", side_effect=fake_info)

        SudoPrime().prime()

        assert calls == ["info", "run"]
        assert "Ctrl-D" in mock_info.call_args.args[0]
        assert "Ctrl-C" not in mock_info.call_args.args[0]

    def test_no_banner_when_sudo_missing(self, mocker) -> None:
        mocker.patch("sysup.capabilities.sudo.shutil.which", return_value=None)
        mocker.patch("sysup.capabilities.sudo.subprocess.run")
        mock_info = mocker.patch("sysup.capabilities.sudo.console.info")

        SudoPrime().prime()

        assert mock_info.call_count == 0

    def test_missing_sudo_returns_noop(self, mocker) -> None:
        mocker.patch("sysup.capabilities.sudo.shutil.which", return_value=None)
        mock_run = mocker.patch("sysup.capabilities.sudo.subprocess.run")

        stop = SudoPrime().prime()
        stop()

        assert mock_run.call_count == 0

    def test_declined_prime_returns_noop(self, mocker) -> None:
        """A declined or failed sudo prompt must not block the update run."""
        mocker.patch("sysup.capabilities.sudo.shutil.which", return_value="/usr/bin/sudo")
        mocker.patch("sysup.capabilities.sudo.subprocess.run", return_value=self._result(returncode=1))
        thread = mocker.patch("sysup.capabilities.sudo.threading.Thread")

        stop = SudoPrime().prime()
        stop()

        assert not thread.called

    def test_run_yields_nothing(self) -> None:
        assert list(SudoPrime().run()) == []

    def test_inputs_empty(self) -> None:
        assert dict(SudoPrime().inputs) == {}

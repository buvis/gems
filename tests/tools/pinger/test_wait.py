from __future__ import annotations

from unittest.mock import call, patch

import pytest
from pinger.commands.wait.exceptions import CommandWaitTimeoutError
from pinger.commands.wait.wait import CommandWait


class TestCommandWaitExecute:
    def test_execute_immediate_response(self):
        cmd = CommandWait(host="example.com", timeout=5)

        with (
            patch("pinger.commands.wait.wait.ping", return_value=0.25) as ping_mock,
            patch("pinger.commands.wait.wait.time.sleep") as sleep_mock,
        ):
            cmd.execute()

        ping_mock.assert_called_once_with("example.com", timeout=1)
        sleep_mock.assert_not_called()

    def test_execute_timeout(self):
        cmd = CommandWait(host="example.com", timeout=2)
        time_values = iter([0, 1, 3])

        with (
            patch("pinger.commands.wait.wait.ping", return_value=None) as ping_mock,
            patch("pinger.commands.wait.wait.time.sleep") as sleep_mock,
            patch("pinger.commands.wait.wait.time.time", side_effect=lambda: next(time_values)),
        ):
            with pytest.raises(CommandWaitTimeoutError):
                cmd.execute()

        assert ping_mock.call_count == 2
        sleep_mock.assert_called_once_with(1)

    def test_execute_responds_after_retries(self):
        cmd = CommandWait(host="example.com", timeout=5)

        with (
            patch("pinger.commands.wait.wait.ping", side_effect=[None, None, 0.25]) as ping_mock,
            patch("pinger.commands.wait.wait.time.sleep") as sleep_mock,
        ):
            cmd.execute()

        assert ping_mock.call_count == 3
        assert sleep_mock.call_count == 2
        sleep_mock.assert_has_calls([call(1), call(1)])

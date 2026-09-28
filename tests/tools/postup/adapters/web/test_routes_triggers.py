"""Trigger-endpoint tests for ``postup serve``.

Asserts the all-interface rule: ``POST /api/actions/collect`` and
``/api/actions/enrich`` drive the *same* command classes as the CLI
(``CommandCollect`` / ``CommandEnrich``) through the composition root — mocked
here — and that a concurrent trigger while a run is active is rejected with an
"already running" status rather than launching a second run.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from buvis.pybase.result import CommandResult
from postup.adapters.web import _routes
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_lock():
    # A fresh, unlocked lock per test so cross-test state never leaks.
    _routes._run_lock = asyncio.Lock()
    yield


TRIGGER_CASES = [
    ("collect", "postup.commands.collect.collect.CommandCollect"),
    ("enrich", "postup.commands.enrich.enrich.CommandEnrich"),
]


class TestTriggerAuth:
    @pytest.mark.parametrize("action", ["collect", "enrich"])
    def test_trigger_without_token_401(self, client: TestClient, action: str) -> None:
        assert client.post(f"/api/actions/{action}").status_code == 401


class TestTriggerRunsSameCommandClass:
    @pytest.mark.parametrize("action,command_path", TRIGGER_CASES, ids=[c[0] for c in TRIGGER_CASES])
    def test_success_runs_command_and_returns_200(self, client: TestClient, action: str, command_path: str) -> None:
        with patch(command_path) as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(success=True, output=f"{action} ok")
            r = client.post(
                f"/api/actions/{action}",
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["output"] == f"{action} ok"
        mock_command.assert_called_once()
        mock_command.return_value.execute.assert_called_once()

    @pytest.mark.parametrize("action,command_path", TRIGGER_CASES, ids=[c[0] for c in TRIGGER_CASES])
    def test_failure_returns_422_with_command_result_message(
        self, client: TestClient, action: str, command_path: str
    ) -> None:
        with patch(command_path) as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(success=False, error=f"{action} failed")
            r = client.post(
                f"/api/actions/{action}",
                headers={"X-Buvis-Token": client.app.state.buvis_token},
            )
        assert r.status_code == 422
        assert r.json()["success"] is False
        assert r.json()["error"] == f"{action} failed"

    def test_collect_receives_the_apps_settings(self, client: TestClient) -> None:
        with patch("postup.commands.collect.collect.CommandCollect") as mock_command:
            mock_command.return_value.execute.return_value = CommandResult(success=True)
            client.post("/api/actions/collect", headers={"X-Buvis-Token": client.app.state.buvis_token})
        called_settings = mock_command.call_args.args[0]
        assert called_settings is client.app.state.settings


class TestConcurrentRunRejected:
    def test_second_run_while_first_holds_lock_is_rejected_409(self) -> None:
        """Drive ``_run_command`` directly: while one run holds the single-run
        lock, a second call must return the 409 "already running" envelope
        without ever building or executing its command."""

        async def _run() -> None:
            release = asyncio.Event()
            first_cmd = MagicMock()

            def _first_execute() -> CommandResult:
                # Runs in a worker thread (asyncio.to_thread); block until the
                # test releases it so the lock stays held meanwhile.
                import time

                while not release.is_set():
                    time.sleep(0.01)
                return CommandResult(success=True, output="first")

            first_cmd.execute.side_effect = _first_execute
            second_build = MagicMock()

            first_task = asyncio.create_task(_routes._run_command(lambda: first_cmd))
            while not _routes._run_lock.locked():
                await asyncio.sleep(0.01)

            second_resp = await _routes._run_command(second_build)
            assert second_resp.status_code == 409
            assert "already running" in second_resp.body.decode()
            second_build.assert_not_called()

            release.set()
            first_resp = await first_task
            assert first_resp.status_code == 200

        asyncio.run(_run())

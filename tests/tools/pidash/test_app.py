from __future__ import annotations

import json
from pathlib import Path

import pytest
from pidash.tui.app import PidashApp
from pidash.tui.watcher import StateChanged, StateFileDeleted


@pytest.fixture
def app(tmp_path: Path) -> PidashApp:
    return PidashApp(project_path=tmp_path, _watch=False)


class TestPidashApp:
    @pytest.mark.anyio
    async def test_starts_in_empty_state(self, app: PidashApp) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.query_one("#header")
            assert "no active" in header.last_text.lower()

    @pytest.mark.anyio
    async def test_state_change_updates_display(self, app: PidashApp, full_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(full_state_dict)))
            await pilot.pause()
            header = app.query_one("#header")
            assert "00010-split-ci" in header.last_text

    @pytest.mark.anyio
    async def test_state_deleted_reverts_to_empty(self, app: PidashApp, full_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(full_state_dict)))
            await pilot.pause()
            app.post_message(StateFileDeleted())
            await pilot.pause()
            header = app.query_one("#header")
            assert "no active" in header.last_text.lower()

    @pytest.mark.anyio
    async def test_malformed_json_keeps_last_state(self, app: PidashApp, full_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(full_state_dict)))
            await pilot.pause()
            app.post_message(StateChanged("{not valid json"))
            await pilot.pause()
            header = app.query_one("#header")
            assert "00010-split-ci" in header.last_text

    @pytest.mark.anyio
    async def test_quit_binding(self, app: PidashApp) -> None:
        async with app.run_test() as pilot:
            await pilot.press("q")
        # App exited cleanly — if we reach here the test passed

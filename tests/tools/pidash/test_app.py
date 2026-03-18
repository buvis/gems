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
    async def test_autopilot_format_updates_display(self, app: PidashApp, autopilot_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(autopilot_state_dict)))
            await pilot.pause()
            header = app.query_one("#header")
            assert "00002-add-feature" in header.last_text

    @pytest.mark.anyio
    async def test_manual_refresh_reads_file(self, app: PidashApp, autopilot_state_dict: dict) -> None:
        state_dir = app._project_path / ".local"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "prd-cycle.json").write_text(json.dumps(autopilot_state_dict))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
            header = app.query_one("#header")
            assert "00002-add-feature" in header.last_text

    @pytest.mark.anyio
    async def test_watcher_loads_existing_file(self, tmp_path: Path, autopilot_state_dict: dict) -> None:
        """Test the real watcher thread reads an existing file on startup."""
        state_dir = tmp_path / ".local"
        state_dir.mkdir()
        (state_dir / "prd-cycle.json").write_text(json.dumps(autopilot_state_dict))
        watch_app = PidashApp(project_path=tmp_path, _watch=True)
        async with watch_app.run_test() as pilot:
            # Give the watcher thread time to read and post the message
            await pilot.pause(delay=0.5)
            header = watch_app.query_one("#header")
            assert "00002-add-feature" in header.last_text, f"Header was: {header.last_text!r}"

    @pytest.mark.anyio
    async def test_quit_binding(self, app: PidashApp) -> None:
        async with app.run_test() as pilot:
            await pilot.press("q")
        # App exited cleanly — if we reach here the test passed

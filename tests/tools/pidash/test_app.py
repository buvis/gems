from __future__ import annotations

import json
from pathlib import Path

import pytest
from pidash.tui.app import PidashApp
from pidash.tui.watcher import StateChanged, StateFileDeleted


@pytest.fixture
def app(tmp_path: Path) -> PidashApp:
    return PidashApp(project_path=tmp_path, _watch=False)


def _pipeline_text(app: PidashApp) -> str:
    return app.query_one("#pipeline").render()


class TestPidashApp:
    @pytest.mark.anyio
    async def test_starts_in_empty_state(self, app: PidashApp) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            text = str(_pipeline_text(app)).lower()
            assert "no active" in text

    @pytest.mark.anyio
    async def test_state_change_updates_display(self, app: PidashApp, full_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(full_state_dict)))
            await pilot.pause()
            text = str(_pipeline_text(app))
            assert "00010-split-ci" in text

    @pytest.mark.anyio
    async def test_state_deleted_reverts_to_empty(self, app: PidashApp, full_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(full_state_dict)))
            await pilot.pause()
            app.post_message(StateFileDeleted())
            await pilot.pause()
            text = str(_pipeline_text(app)).lower()
            assert "no active" in text

    @pytest.mark.anyio
    async def test_malformed_json_keeps_last_state(self, app: PidashApp, full_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(full_state_dict)))
            await pilot.pause()
            app.post_message(StateChanged("{not valid json"))
            await pilot.pause()
            text = str(_pipeline_text(app))
            assert "00010-split-ci" in text

    @pytest.mark.anyio
    async def test_autopilot_format_updates_display(self, app: PidashApp, autopilot_state_dict: dict) -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(autopilot_state_dict)))
            await pilot.pause()
            text = str(_pipeline_text(app))
            assert "00002-add-feature" in text

    @pytest.mark.anyio
    async def test_manual_refresh_reads_file(self, app: PidashApp, autopilot_state_dict: dict) -> None:
        state_dir = app._project_path / "dev" / "local" / "autopilot"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "state.json").write_text(json.dumps(autopilot_state_dict))
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()
            text = str(_pipeline_text(app))
            assert "00002-add-feature" in text

    @pytest.mark.anyio
    async def test_watcher_loads_existing_file(self, tmp_path: Path, autopilot_state_dict: dict) -> None:
        state_dir = tmp_path / "dev" / "local" / "autopilot"
        state_dir.mkdir(parents=True)
        (state_dir / "state.json").write_text(json.dumps(autopilot_state_dict))
        watch_app = PidashApp(project_path=tmp_path, _watch=True)
        async with watch_app.run_test() as pilot:
            await pilot.pause(delay=0.5)
            text = str(_pipeline_text(watch_app))
            assert "00002-add-feature" in text, f"Pipeline was: {text!r}"

    @pytest.mark.anyio
    async def test_quit_binding(self, app: PidashApp) -> None:
        async with app.run_test() as pilot:
            await pilot.press("q")

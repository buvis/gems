from __future__ import annotations

import json
from pathlib import Path

import pytest
from pidash.tui.app import PidashApp
from pidash.tui.watcher import SessionRemoved, SessionUpdated, StateChanged, StateFileDeleted


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


def _session_json(
    session_id: str,
    cwd: str,
    phase: str = "work",
    prd_name: str = "test-prd",
    needs_attention: bool = False,
    updated_at: str = "2026-04-01T12:00:00+00:00",
) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "cwd": cwd,
            "updated_at": updated_at,
            "prd": {"name": prd_name},
            "phase": phase,
            "needs_attention": needs_attention,
            "tasks_total": 5,
            "tasks_completed": 2,
            "tasks": [],
            "phases_completed": [],
            "cycle": 1,
            "autonomous_decisions": [],
            "deferred_decisions": [],
            "doubts": [],
            "review_cycles": [],
        }
    )


class TestMultiSessionApp:
    @pytest.mark.anyio
    async def test_starts_with_no_sessions_message(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            text = str(app.query_one("#sidebar").render()).lower()
            assert "no active sessions" in text

    @pytest.mark.anyio
    async def test_session_added_appears_in_sidebar(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(SessionUpdated("s1", _session_json("s1", "/tmp/proj-alpha", prd_name="alpha-prd")))
            await pilot.pause()
            text = str(app.query_one("#sidebar").render())
            assert "proj-alpha" in text

    @pytest.mark.anyio
    async def test_session_removed_disappears(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(SessionUpdated("s1", _session_json("s1", "/tmp/proj-alpha")))
            await pilot.pause()
            app.post_message(SessionRemoved("s1"))
            await pilot.pause()
            text = str(app.query_one("#sidebar").render()).lower()
            assert "proj-alpha" not in text
            assert "no active sessions" in text

    @pytest.mark.anyio
    async def test_session_switch_updates_detail(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(SessionUpdated("s1", _session_json("s1", "/tmp/proj-alpha", prd_name="alpha-prd")))
            await pilot.pause()
            app.post_message(SessionUpdated("s2", _session_json("s2", "/tmp/proj-beta", prd_name="beta-prd")))
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            text = str(_pipeline_text(app))
            assert "beta-prd" in text

    @pytest.mark.anyio
    async def test_attention_indicator_in_sidebar(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(
                SessionUpdated("s1", _session_json("s1", "/tmp/proj-urgent", needs_attention=True))
            )
            await pilot.pause()
            text = str(app.query_one("#sidebar").render())
            assert "\u25cf" in text

    @pytest.mark.anyio
    async def test_single_project_mode_unchanged(self, tmp_path: Path) -> None:
        app = PidashApp(project_path=tmp_path, _watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            text = str(_pipeline_text(app)).lower()
            assert "no active" in text

    @pytest.mark.anyio
    async def test_footer_shows_session_count(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.post_message(SessionUpdated("s1", _session_json("s1", "/tmp/proj-alpha")))
            await pilot.pause()
            text = str(app.query_one("#footer").render())
            assert "sessions" in text.lower()

    @pytest.mark.anyio
    async def test_stale_session_detected(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            old_ts = "2020-01-01T00:00:00+00:00"
            app.post_message(SessionUpdated("s1", _session_json("s1", "/tmp/stale-proj", updated_at=old_ts)))
            await pilot.pause()
            app._check_stale()
            assert "s1" in app._stale_ids

    @pytest.mark.anyio
    async def test_done_session_not_stale(self) -> None:
        app = PidashApp(_watch=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            old_ts = "2020-01-01T00:00:00+00:00"
            app.post_message(
                SessionUpdated("s1", _session_json("s1", "/tmp/done-proj", phase="done", updated_at=old_ts))
            )
            await pilot.pause()
            app._check_stale()
            assert "s1" not in app._stale_ids

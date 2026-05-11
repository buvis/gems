from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pidash.hooks import session as session_mod
from pidash.hooks.sync_agent_return import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _state_path(repo_root: Path) -> Path:
    return repo_root / "dev" / "local" / "autopilot" / "state.json"


def _seed_state(repo_root: Path, tasks: list[dict[str, object]]) -> Path:
    state_path = _state_path(repo_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"tasks": tasks, "tasks_total": len(tasks), "tasks_completed": 0}, indent=2) + "\n",
        encoding="utf-8",
    )
    return state_path


def _run_with_stdin(payload: dict[str, object], mocker: MockerFixture) -> None:
    mocker.patch("sys.stdin", io.StringIO(json.dumps(payload)))
    main()


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    return tmp_path


class TestSyncAgentReturnHook:
    def test_check_mark_marker_completes_task(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(
            sandbox,
            [
                {"name": "Task A", "status": "pending"},
                {"name": "Task B", "status": "pending"},
            ],
        )
        _run_with_stdin({"tool_response": "✓ Task A\n✅ Task B\nSome other output."}, mocker)
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "completed"
        assert state["tasks"][1]["status"] == "completed"
        assert state["tasks_completed"] == 2

    def test_checkbox_marker_completes_task(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "Task A", "status": "pending"}])
        _run_with_stdin({"tool_response": "- [x] Task A"}, mocker)
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "completed"

    def test_checkbox_marker_case_insensitive(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "Task A", "status": "pending"}])
        _run_with_stdin({"tool_response": "- [X] Task A"}, mocker)
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "completed"

    def test_in_progress_marker_upgrades_pending(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "Task B", "status": "pending"}])
        _run_with_stdin({"tool_response": "■ Task B"}, mocker)
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "in_progress"

    def test_in_progress_does_not_overwrite_completed(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "Task A", "status": "completed"}])
        before = state_path.read_text()
        _run_with_stdin({"tool_response": "■ Task A"}, mocker)
        assert state_path.read_text() == before

    def test_prefix_match(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "[C1] Task C", "status": "pending"}])
        _run_with_stdin({"tool_response": "✓ Task C"}, mocker)
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "completed"

    def test_no_markers_no_op(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "Task A", "status": "pending"}])
        before = state_path.read_text()
        _run_with_stdin({"tool_response": "no markers here"}, mocker)
        assert state_path.read_text() == before

    def test_state_missing_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        _run_with_stdin({"tool_response": "✓ Task A"}, mocker)
        assert not _state_path(sandbox).exists()

    def test_invalid_stdin_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "Task A", "status": "pending"}])
        before = state_path.read_text()
        mocker.patch("sys.stdin", io.StringIO("not json"))
        main()
        assert state_path.read_text() == before

    def test_tty_stdin_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        """Hook returns early when stdin is a TTY (no piped input from Claude Code)."""
        state_path = _seed_state(sandbox, [{"name": "Task A", "status": "pending"}])
        before = state_path.read_text()
        fake_stdin = mocker.MagicMock()
        fake_stdin.isatty.return_value = True
        mocker.patch("sys.stdin", fake_stdin)
        main()
        fake_stdin.read.assert_not_called()
        assert state_path.read_text() == before

    def test_empty_response_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"name": "Task A", "status": "pending"}])
        before = state_path.read_text()
        _run_with_stdin({"tool_response": ""}, mocker)
        assert state_path.read_text() == before

    def test_mirror_writes_session_file(self, sandbox: Path, mocker: MockerFixture) -> None:
        _seed_state(sandbox, [{"name": "Task A", "status": "pending"}])
        _run_with_stdin(
            {"tool_response": "✓ Task A", "session_id": "abc", "cwd": str(sandbox)},
            mocker,
        )
        session_file = sandbox / "sessions" / "abc.json"
        assert session_file.is_file()
        data = json.loads(session_file.read_text())
        assert data["tasks"][0]["status"] == "completed"

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pidash.hooks import session as session_mod
from pidash.hooks.update_tasks import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _state_path(repo_root: Path) -> Path:
    return repo_root / "dev" / "local" / "autopilot" / "state.json"


def _seed_state(repo_root: Path, tasks: list[dict[str, object]]) -> Path:
    state_path = _state_path(repo_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "tasks": tasks,
                "tasks_total": len(tasks),
                "tasks_completed": sum(1 for t in tasks if t.get("status") == "completed"),
            },
            indent=2,
        )
        + "\n",
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


class TestUpdateTasksHook:
    def test_match_by_id(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(
            sandbox,
            [
                {"id": "1", "name": "First", "status": "pending"},
                {"id": "2", "name": "Second", "status": "pending"},
            ],
        )
        _run_with_stdin(
            {"tool_input": {"id": "1", "status": "completed"}, "tool_response": ""},
            mocker,
        )
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "completed"
        assert state["tasks"][1]["status"] == "pending"
        assert state["tasks_completed"] == 1
        assert state["tasks_total"] == 2

    def test_match_by_response_title(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(
            sandbox,
            [
                {"id": "old-1", "name": "Add validation", "status": "pending"},
                {"id": "old-2", "name": "Update docs", "status": "pending"},
            ],
        )
        _run_with_stdin(
            {
                "tool_input": {"id": "fresh-uuid", "status": "in_progress"},
                "tool_response": {"title": "Add validation"},
            },
            mocker,
        )
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "in_progress"
        # Strategy 2 backfills the new id
        assert state["tasks"][0]["id"] == "fresh-uuid"

    def test_match_by_response_substring(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(
            sandbox,
            [{"id": "x", "name": "Wire integration tests", "status": "pending"}],
        )
        _run_with_stdin(
            {
                "tool_input": {"id": "new-id", "status": "completed"},
                "tool_response": "Marking Wire integration tests as done.",
            },
            mocker,
        )
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "completed"

    def test_prefix_stripping(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(
            sandbox,
            [{"id": "x", "name": "[C1] Refactor parser", "status": "pending"}],
        )
        _run_with_stdin(
            {
                "tool_input": {"id": "new-id", "status": "completed"},
                "tool_response": {"title": "Refactor parser"},
            },
            mocker,
        )
        state = json.loads(state_path.read_text())
        assert state["tasks"][0]["status"] == "completed"

    def test_no_match_is_silent(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(
            sandbox,
            [{"id": "x", "name": "Known task", "status": "pending"}],
        )
        before = state_path.read_text()
        _run_with_stdin(
            {"tool_input": {"id": "unknown-id", "status": "completed"}, "tool_response": ""},
            mocker,
        )
        assert state_path.read_text() == before

    def test_state_missing_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        _run_with_stdin(
            {"tool_input": {"id": "1", "status": "completed"}, "tool_response": ""},
            mocker,
        )
        assert not _state_path(sandbox).exists()

    def test_invalid_stdin_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(
            sandbox,
            [{"id": "1", "name": "T", "status": "pending"}],
        )
        before = state_path.read_text()
        mocker.patch("sys.stdin", io.StringIO("not json"))
        main()
        assert state_path.read_text() == before

    def test_missing_tool_input_id_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, [{"id": "1", "name": "T", "status": "pending"}])
        before = state_path.read_text()
        _run_with_stdin({"tool_input": {"status": "completed"}, "tool_response": ""}, mocker)
        assert state_path.read_text() == before

    def test_mirror_writes_session_file(self, sandbox: Path, mocker: MockerFixture) -> None:
        _seed_state(sandbox, [{"id": "1", "name": "T", "status": "pending"}])
        _run_with_stdin(
            {
                "tool_input": {"id": "1", "status": "completed"},
                "tool_response": "",
                "session_id": "abc",
                "cwd": str(sandbox),
            },
            mocker,
        )
        session_file = sandbox / "sessions" / "abc.json"
        assert session_file.is_file()
        data = json.loads(session_file.read_text())
        assert data["session_id"] == "abc"
        assert data["tasks"][0]["status"] == "completed"

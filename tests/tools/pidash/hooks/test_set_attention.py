from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pidash.hooks import session as session_mod
from pidash.hooks.set_attention import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _state_path(repo_root: Path) -> Path:
    return repo_root / "dev" / "local" / "autopilot" / "state.json"


def _seed_state(repo_root: Path, **overrides: object) -> Path:
    state_path = _state_path(repo_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state: dict[str, object] = {
        "tasks": [],
        "tasks_total": 0,
        "tasks_completed": 0,
        "needs_attention": False,
    }
    state.update(overrides)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state_path


def _run_with_stdin(payload: dict[str, object], mocker: MockerFixture) -> None:
    mocker.patch("sys.stdin", io.StringIO(json.dumps(payload)))
    main()


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    return tmp_path


class TestSetAttentionHook:
    def test_flips_needs_attention_to_true(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, needs_attention=False)
        _run_with_stdin({"session_id": "s1", "cwd": str(sandbox)}, mocker)
        state = json.loads(state_path.read_text())
        assert state["needs_attention"] is True

    def test_mirrors_to_session_file(self, sandbox: Path, mocker: MockerFixture) -> None:
        """Session file shape from PRD happy-path scenario:
        session_id, cwd, tasks, needs_attention, updated_at."""
        _seed_state(
            sandbox,
            tasks=[
                {"id": "1", "name": "T", "status": "pending"},
            ],
            tasks_total=1,
            tasks_completed=0,
        )
        _run_with_stdin({"session_id": "abc", "cwd": str(sandbox)}, mocker)
        session_file = sandbox / "sessions" / "abc.json"
        assert session_file.is_file()
        data = json.loads(session_file.read_text())
        assert data["session_id"] == "abc"
        assert data["cwd"] == str(sandbox)
        assert data["needs_attention"] is True
        assert data["tasks"] == [{"id": "1", "name": "T", "status": "pending"}]
        assert "updated_at" in data

    def test_atomic_write_failure_does_not_corrupt_either_file(self, sandbox: Path, mocker: MockerFixture) -> None:
        """Both state.json and session-file writes share fate: when
        ``os.replace`` fails, neither target gets a partial write.
        The seeded state.json content stays intact."""
        state_path = _seed_state(sandbox, needs_attention=False)
        before = state_path.read_text()
        mocker.patch("os.replace", side_effect=OSError("disk full"))
        _run_with_stdin({"session_id": "abc", "cwd": str(sandbox)}, mocker)
        assert state_path.read_text() == before
        assert not (sandbox / "sessions" / "abc.json").is_file()
        assert [p.name for p in state_path.parent.iterdir()] == ["state.json"]
        sessions_dir = sandbox / "sessions"
        assert not sessions_dir.exists() or list(sessions_dir.iterdir()) == []

    def test_state_missing_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        _run_with_stdin({"session_id": "abc"}, mocker)
        assert not _state_path(sandbox).exists()

    def test_empty_stdin_still_updates_state_but_skips_session_mirror(
        self, sandbox: Path, mocker: MockerFixture
    ) -> None:
        """Without a session_id we can't mirror, but state.json still flips
        (the dashboard reads state.json directly in single-project mode)."""
        state_path = _seed_state(sandbox, needs_attention=False)
        mocker.patch("sys.stdin", io.StringIO(""))
        main()
        state = json.loads(state_path.read_text())
        assert state["needs_attention"] is True
        assert not (sandbox / "sessions").exists()

    def test_malformed_state_json_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _state_path(sandbox)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{ broken", encoding="utf-8")
        before = state_path.read_text()
        _run_with_stdin({"session_id": "s1"}, mocker)
        assert state_path.read_text() == before

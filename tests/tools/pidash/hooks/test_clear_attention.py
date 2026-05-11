from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pidash.hooks import session as session_mod
from pidash.hooks.clear_attention import main

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
        "needs_attention": True,
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


class TestClearAttentionHook:
    def test_flips_needs_attention_to_false(self, sandbox: Path, mocker: MockerFixture) -> None:
        state_path = _seed_state(sandbox, needs_attention=True)
        _run_with_stdin({"session_id": "s1"}, mocker)
        state = json.loads(state_path.read_text())
        assert state["needs_attention"] is False

    def test_skips_write_when_already_false(self, sandbox: Path, mocker: MockerFixture) -> None:
        """Avoid storming state.json on every PostToolUse when nothing needs clearing."""
        state_path = _seed_state(sandbox, needs_attention=False)
        before = state_path.read_text()
        _run_with_stdin({"session_id": "s1"}, mocker)
        assert state_path.read_text() == before

    def test_mirrors_to_session_file_when_clearing(self, sandbox: Path, mocker: MockerFixture) -> None:
        _seed_state(sandbox, needs_attention=True)
        _run_with_stdin({"session_id": "abc", "cwd": str(sandbox)}, mocker)
        session_file = sandbox / "sessions" / "abc.json"
        assert session_file.is_file()
        data = json.loads(session_file.read_text())
        assert data["needs_attention"] is False

    def test_state_missing_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        _run_with_stdin({"session_id": "abc"}, mocker)
        assert not _state_path(sandbox).exists()

    def test_empty_stdin_still_clears_state_but_skips_session_mirror(
        self, sandbox: Path, mocker: MockerFixture
    ) -> None:
        """Without a session_id we can't mirror, but state.json still clears."""
        state_path = _seed_state(sandbox, needs_attention=True)
        mocker.patch("sys.stdin", io.StringIO(""))
        main()
        state = json.loads(state_path.read_text())
        assert state["needs_attention"] is False
        assert not (sandbox / "sessions").exists()

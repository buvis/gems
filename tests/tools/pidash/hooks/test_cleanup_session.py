from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pidash.hooks import cleanup_session as cleanup_mod, session as session_mod
from pidash.hooks.cleanup_session import main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _run_with_stdin(payload: dict[str, object], mocker: MockerFixture) -> None:
    mocker.patch("sys.stdin", io.StringIO(json.dumps(payload)))
    main()


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    sessions_dir = tmp_path / "sessions"
    # cleanup_session.py binds SESSIONS_DIR at import; patch both modules.
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(cleanup_mod, "SESSIONS_DIR", sessions_dir)
    return tmp_path


class TestCleanupSessionHook:
    def test_marks_existing_session_stopped(self, sandbox: Path, mocker: MockerFixture) -> None:
        sessions_dir = sandbox / "sessions"
        sessions_dir.mkdir()
        target = sessions_dir / "s1.json"
        target.write_text(json.dumps({"session_id": "s1", "phase": "work"}), encoding="utf-8")
        _run_with_stdin({"session_id": "s1"}, mocker)
        data = json.loads(target.read_text())
        assert data["phase"] == "stopped"
        assert "stopped_at" in data
        assert "updated_at" in data

    def test_creates_minimal_record_when_session_file_absent(self, sandbox: Path, mocker: MockerFixture) -> None:
        _run_with_stdin({"session_id": "fresh", "cwd": "/some/repo"}, mocker)
        target = sandbox / "sessions" / "fresh.json"
        assert target.is_file()
        data = json.loads(target.read_text())
        assert data["session_id"] == "fresh"
        assert data["cwd"] == "/some/repo"
        assert data["phase"] == "stopped"
        assert "stopped_at" in data

    def test_missing_session_id_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        _run_with_stdin({"cwd": "/x"}, mocker)
        assert not (sandbox / "sessions").exists()

    def test_empty_session_id_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        _run_with_stdin({"session_id": ""}, mocker)
        assert not (sandbox / "sessions").exists()

    def test_null_byte_session_id_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        # Embedded null bytes are not valid in filesystem paths and would raise
        # ``ValueError`` (not ``OSError``) inside ``tempfile.mkstemp``. Reject
        # up-front so the hook stays a silent no-op.
        _run_with_stdin({"session_id": "abc\x00def"}, mocker)
        assert not (sandbox / "sessions").exists()

    def test_path_traversal_in_session_id_is_stripped(self, sandbox: Path, mocker: MockerFixture) -> None:
        """``Path(session_id).name`` must collapse traversal attempts to a basename."""
        _run_with_stdin({"session_id": "../../../etc/passwd"}, mocker)
        sessions_dir = sandbox / "sessions"
        assert sessions_dir.is_dir()
        produced = list(sessions_dir.glob("*.json"))
        assert len(produced) == 1
        assert produced[0].name == "passwd.json"
        assert not (sandbox.parent / "etc" / "passwd").exists()

    def test_empty_stdin_is_noop(self, sandbox: Path, mocker: MockerFixture) -> None:
        mocker.patch("sys.stdin", io.StringIO(""))
        main()
        assert not (sandbox / "sessions").exists()

    def test_corrupt_existing_session_file_falls_back_to_minimal_record(
        self, sandbox: Path, mocker: MockerFixture
    ) -> None:
        sessions_dir = sandbox / "sessions"
        sessions_dir.mkdir()
        target = sessions_dir / "s1.json"
        target.write_text("not json at all", encoding="utf-8")
        _run_with_stdin({"session_id": "s1", "cwd": "/r"}, mocker)
        data = json.loads(target.read_text())
        assert data["session_id"] == "s1"
        assert data["phase"] == "stopped"

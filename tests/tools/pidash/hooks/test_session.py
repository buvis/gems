from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pidash.hooks import session as session_mod
from pidash.hooks.session import (
    SESSIONS_DIR,
    mirror_to_session_dir,
    read_hook_input,
    write_session_file,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class TestReadHookInput:
    def test_tty_stdin_returns_empty_dict(self, mocker: MockerFixture) -> None:
        mocker.patch("sys.stdin.isatty", return_value=True)
        assert read_hook_input() == {}

    def test_empty_stdin_returns_empty_dict(self, mocker: MockerFixture) -> None:
        mocker.patch("sys.stdin.isatty", return_value=False)
        mocker.patch("sys.stdin", io.StringIO(""))
        assert read_hook_input() == {}

    def test_whitespace_only_stdin_returns_empty_dict(self, mocker: MockerFixture) -> None:
        mocker.patch("sys.stdin.isatty", return_value=False)
        mocker.patch("sys.stdin", io.StringIO("   \n\t  "))
        assert read_hook_input() == {}

    def test_malformed_json_returns_empty_dict(self, mocker: MockerFixture) -> None:
        mocker.patch("sys.stdin.isatty", return_value=False)
        mocker.patch("sys.stdin", io.StringIO("not json"))
        assert read_hook_input() == {}

    def test_valid_json_returns_parsed_dict(self, mocker: MockerFixture) -> None:
        mocker.patch("sys.stdin.isatty", return_value=False)
        mocker.patch("sys.stdin", io.StringIO('{"session_id": "abc", "cwd": "/r"}'))
        assert read_hook_input() == {"session_id": "abc", "cwd": "/r"}

    def test_top_level_non_dict_returns_empty(self, mocker: MockerFixture) -> None:
        mocker.patch("sys.stdin.isatty", return_value=False)
        mocker.patch("sys.stdin", io.StringIO("[1, 2, 3]"))
        assert read_hook_input() == {}


class TestMirrorToSessionDir:
    @pytest.fixture(autouse=True)
    def _sandbox_sessions_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        sandbox = tmp_path / "sessions"
        monkeypatch.setattr(session_mod, "SESSIONS_DIR", sandbox)
        self._sandbox = sandbox

    def test_missing_session_id_is_silent_no_op(self) -> None:
        mirror_to_session_dir({}, {"phase": "work"})
        assert not self._sandbox.exists()

    def test_empty_string_session_id_is_silent_no_op(self) -> None:
        mirror_to_session_dir({"session_id": ""}, {"phase": "work"})
        assert not self._sandbox.exists()

    def test_non_string_session_id_is_silent_no_op(self) -> None:
        mirror_to_session_dir({"session_id": 123}, {"phase": "work"})
        assert not self._sandbox.exists()

    def test_session_id_with_separator_is_stripped_to_basename(self) -> None:
        mirror_to_session_dir({"session_id": "subdir/abc123"}, {"phase": "work"})
        assert (self._sandbox / "abc123.json").is_file()
        assert not (self._sandbox / "subdir").exists()

    def test_writes_merged_state_with_required_fields(self) -> None:
        mirror_to_session_dir(
            {"session_id": "s1", "cwd": "/repo"},
            {"phase": "work", "cycle": 2, "tasks_total": 5},
        )
        data = json.loads((self._sandbox / "s1.json").read_text(encoding="utf-8"))
        assert data["session_id"] == "s1"
        assert data["cwd"] == "/repo"
        assert data["phase"] == "work"
        assert data["cycle"] == 2
        assert data["tasks_total"] == 5
        assert "updated_at" in data
        assert "+00:00" in data["updated_at"]

    def test_cwd_defaults_to_empty_string_when_missing(self) -> None:
        mirror_to_session_dir({"session_id": "s1"}, {"phase": "stopped"})
        data = json.loads((self._sandbox / "s1.json").read_text(encoding="utf-8"))
        assert data["cwd"] == ""

    def test_creates_sessions_dir_when_missing(self) -> None:
        assert not self._sandbox.exists()
        mirror_to_session_dir({"session_id": "s1"}, {})
        assert self._sandbox.is_dir()

    def test_does_not_mutate_caller_state_dict(self) -> None:
        state = {"phase": "work"}
        mirror_to_session_dir({"session_id": "s1", "cwd": "/r"}, state)
        assert state == {"phase": "work"}


class TestWriteSessionFile:
    def test_writes_json_with_trailing_newline(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        write_session_file(target, {"a": 1, "b": "two"})
        raw = target.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        assert json.loads(raw) == {"a": 1, "b": "two"}

    def test_indent_is_two_spaces(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        write_session_file(target, {"a": 1})
        raw = target.read_text(encoding="utf-8")
        assert '  "a": 1' in raw

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        target.write_text('{"old": true}\n', encoding="utf-8")
        write_session_file(target, {"new": True})
        assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}

    def test_swallows_oserror_when_target_dir_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "missing-parent" / "out.json"
        write_session_file(target, {"a": 1})
        assert not target.exists()
        assert list(tmp_path.iterdir()) == []

    def test_cleans_up_tempfile_when_replace_fails(self, tmp_path: Path, mocker: MockerFixture) -> None:
        target = tmp_path / "out.json"
        mocker.patch("os.replace", side_effect=OSError("boom"))
        write_session_file(target, {"a": 1})
        assert not target.exists()
        # tempfile must not leak into the target directory
        leftovers = [p for p in tmp_path.iterdir() if p.name.startswith("out.")]
        assert leftovers == []


class TestSessionsDirConstant:
    def test_default_points_to_user_home_pidash_sessions(self) -> None:
        assert SESSIONS_DIR == Path.home() / ".pidash" / "sessions"

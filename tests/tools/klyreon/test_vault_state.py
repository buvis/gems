"""Vault state file ($XDG_STATE_HOME/klyreon/state.json)."""

from __future__ import annotations

from pathlib import Path

import pytest
from klyreon.vault.state import read_state, state_path, write_state


class TestState:
    def test_absent_state_is_empty_dict(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        assert read_state() == {}

    def test_write_then_read_round_trips(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        write_state({"last_maintain": "2026-04-11T15:00:00+02:00"})
        assert read_state()["last_maintain"] == "2026-04-11T15:00:00+02:00"

    def test_state_path_honours_xdg(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "s"))
        assert state_path() == tmp_path / "s" / "klyreon" / "state.json"

    def test_corrupt_state_reads_as_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        path = state_path()
        path.parent.mkdir(parents=True)
        path.write_text("{ not json")
        assert read_state() == {}

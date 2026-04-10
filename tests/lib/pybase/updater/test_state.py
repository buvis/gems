"""Tests for the updater state store (cache + log)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from buvis.pybase.updater.state import (
    STATE_FILE_NAME,
    append_log,
    read_cache,
    write_cache,
)


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestReadCache:
    def test_returns_none_when_file_missing(self, state_dir: Path) -> None:
        assert read_cache(state_dir) == (None, None)

    def test_returns_none_when_file_corrupt(self, state_dir: Path) -> None:
        (state_dir / STATE_FILE_NAME).write_text("not json{{{")
        assert read_cache(state_dir) == (None, None)

    def test_returns_none_when_fields_missing(self, state_dir: Path) -> None:
        (state_dir / STATE_FILE_NAME).write_text(json.dumps({"log": []}))
        assert read_cache(state_dir) == (None, None)

    def test_returns_cached_values(self, state_dir: Path) -> None:
        now = datetime.now(tz=timezone.utc)
        (state_dir / STATE_FILE_NAME).write_text(json.dumps({"last_check": now.isoformat(), "latest_version": "1.2.3"}))
        last_check, latest_version = read_cache(state_dir)
        assert last_check == now
        assert latest_version == "1.2.3"

    def test_naive_timestamp_treated_as_utc(self, state_dir: Path) -> None:
        (state_dir / STATE_FILE_NAME).write_text(
            json.dumps({"last_check": "2026-01-01T00:00:00", "latest_version": "1.0.0"})
        )
        last_check, _ = read_cache(state_dir)
        assert last_check is not None
        assert last_check.tzinfo is timezone.utc


class TestWriteCache:
    def test_creates_state_dir(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "nested" / "config"
        write_cache(state_dir, "1.0.0")
        assert (state_dir / STATE_FILE_NAME).exists()

    def test_updates_cache_fields(self, state_dir: Path) -> None:
        write_cache(state_dir, "1.0.0")
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert state["latest_version"] == "1.0.0"
        assert "last_check" in state

    def test_preserves_existing_log(self, state_dir: Path) -> None:
        (state_dir / STATE_FILE_NAME).write_text(
            json.dumps(
                {
                    "last_check": "2020-01-01T00:00:00+00:00",
                    "latest_version": "0.1.0",
                    "log": [{"ts": "2020-01-01T00:00:00+00:00", "level": "info", "message": "prior"}],
                }
            )
        )
        write_cache(state_dir, "0.2.0")
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert state["latest_version"] == "0.2.0"
        assert state["log"] == [{"ts": "2020-01-01T00:00:00+00:00", "level": "info", "message": "prior"}]


class TestAppendLog:
    def test_creates_file_when_missing(self, state_dir: Path) -> None:
        append_log(state_dir, "info", "first message")
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert len(state["log"]) == 1
        entry = state["log"][0]
        assert entry["level"] == "info"
        assert entry["message"] == "first message"
        assert "ts" in entry

    def test_appends_to_existing_log(self, state_dir: Path) -> None:
        append_log(state_dir, "info", "first")
        append_log(state_dir, "error", "second")
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert len(state["log"]) == 2
        assert state["log"][0]["message"] == "first"
        assert state["log"][1]["message"] == "second"
        assert state["log"][1]["level"] == "error"

    def test_preserves_cache_fields(self, state_dir: Path) -> None:
        write_cache(state_dir, "1.0.0")
        append_log(state_dir, "info", "event")
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert state["latest_version"] == "1.0.0"
        assert len(state["log"]) == 1

    def test_caps_log_at_100_entries(self, state_dir: Path) -> None:
        for i in range(150):
            append_log(state_dir, "info", f"event {i}")
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert len(state["log"]) == 100
        # Oldest entries were dropped
        assert state["log"][0]["message"] == "event 50"
        assert state["log"][-1]["message"] == "event 149"

    def test_recovers_from_corrupt_log_field(self, state_dir: Path) -> None:
        (state_dir / STATE_FILE_NAME).write_text(json.dumps({"log": "not a list"}))
        append_log(state_dir, "info", "recovered")
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert state["log"] == [
            {"ts": state["log"][0]["ts"], "level": "info", "message": "recovered"},
        ]

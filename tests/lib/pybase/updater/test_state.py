"""Tests for the updater state store (cache + log)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from buvis.pybase.updater.state import (
    STATE_FILE_NAME,
    append_log,
    clear_upgrade_failure,
    read_cache,
    read_installer_cache,
    read_upgrade_failure,
    write_cache,
    write_installer_cache,
    write_upgrade_failure,
)
from pytest_mock import MockerFixture


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

    def test_replace_failure_leaves_existing_state_byte_for_byte_intact(
        self, state_dir: Path, mocker: MockerFixture
    ) -> None:
        state_path = state_dir / STATE_FILE_NAME
        state_path.write_text(json.dumps({"last_check": "2020-01-01T00:00:00+00:00", "latest_version": "0.1.0"}))
        original_bytes = state_path.read_bytes()

        # _write_state swallows all exceptions, so a failed swap must not
        # raise here — but it must also not have truncated the existing file.
        mocker.patch(
            "buvis.pybase.filesystem.atomic_write.os.replace",
            side_effect=OSError("simulated swap failure"),
        )

        write_cache(state_dir, "9.9.9")

        assert state_path.read_bytes() == original_bytes

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


def _seconds_ago(ts: datetime | None) -> float:
    assert ts is not None
    return (datetime.now(tz=timezone.utc) - ts).total_seconds()


class TestUpgradeFailure:
    def test_upgrade_failure_roundtrip_preserves_cache_and_log(self, state_dir: Path) -> None:
        write_cache(state_dir, "0.14.1")
        append_log(state_dir, "info", "prior")

        write_upgrade_failure(state_dir, "0.14.1")

        failure = read_upgrade_failure(state_dir)
        assert failure is not None
        assert failure[0] == "0.14.1"
        assert 0 <= _seconds_ago(failure[1]) < 5
        assert read_cache(state_dir)[1] == "0.14.1"
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert [entry["message"] for entry in state["log"]] == ["prior"]

    def test_clear_upgrade_failure_removes_key(self, state_dir: Path) -> None:
        write_cache(state_dir, "0.14.1")
        write_upgrade_failure(state_dir, "0.14.1")

        clear_upgrade_failure(state_dir)

        assert read_upgrade_failure(state_dir) is None
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert "upgrade_failed" not in state
        assert state["latest_version"] == "0.14.1"


class TestInstallerCache:
    @pytest.mark.parametrize("installer_first", [True, False], ids=["installer-first", "pypi-first"])
    def test_installer_cache_preserves_pypi_cache_log_and_backoff(self, state_dir: Path, installer_first: bool) -> None:
        append_log(state_dir, "info", "prior")
        write_upgrade_failure(state_dir, "0.14.0")

        writes = [
            lambda: write_installer_cache(state_dir, "mise-pipx", "0.13.0"),
            lambda: write_cache(state_dir, "0.14.1"),
        ]
        for write in writes if installer_first else reversed(writes):
            write()

        pypi_check, pypi_version = read_cache(state_dir)
        installer_check, installer_version = read_installer_cache(state_dir, "mise-pipx")
        assert pypi_version == "0.14.1"
        assert installer_version == "0.13.0"
        assert 0 <= _seconds_ago(pypi_check) < 5
        assert 0 <= _seconds_ago(installer_check) < 5
        failure = read_upgrade_failure(state_dir)
        assert failure is not None and failure[0] == "0.14.0"
        state = json.loads((state_dir / STATE_FILE_NAME).read_text())
        assert [entry["message"] for entry in state["log"]] == ["prior"]

    @pytest.mark.parametrize(
        "state",
        [
            {},
            {"last_check": "2026-10-12T00:00:00+00:00", "latest_version": "0.14.1"},
            {"installer_cache": "not a dict"},
            {"installer_cache": {"method": "mise-pipx", "last_check": "garbage", "latest_version": "0.13.0"}},
            {"installer_cache": {"method": "mise-pipx", "last_check": "2026-10-12T00:00:00+00:00"}},
            {
                "installer_cache": {
                    "method": "mise-pipx",
                    "last_check": "2026-10-12T00:00:00+00:00",
                    "latest_version": 1,
                }
            },
            {
                "installer_cache": {
                    "method": "uv-tool",
                    "last_check": "2026-10-12T00:00:00+00:00",
                    "latest_version": "1",
                }
            },
        ],
        ids=["absent", "legacy-pypi-only", "not-a-dict", "bad-ts", "no-version", "non-str-version", "other-method"],
    )
    def test_installer_cache_missing_malformed_or_method_mismatch_is_miss(
        self, state_dir: Path, state: dict[str, Any]
    ) -> None:
        (state_dir / STATE_FILE_NAME).write_text(json.dumps(state))

        assert read_installer_cache(state_dir, "mise-pipx") == (None, None)

    def test_naive_installer_timestamp_treated_as_utc(self, state_dir: Path) -> None:
        record = {"method": "mise-pipx", "last_check": "2026-10-12T00:00:00", "latest_version": "0.13.0"}
        (state_dir / STATE_FILE_NAME).write_text(json.dumps({"installer_cache": record}))

        last_check, version = read_installer_cache(state_dir, "mise-pipx")

        assert version == "0.13.0"
        assert last_check == datetime(2026, 10, 12, tzinfo=timezone.utc)

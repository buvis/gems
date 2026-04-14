"""Tests for version checking and cache management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater.checker import check_for_update, fetch_latest_version


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    return tmp_path


def _mock_pypi_response(version: str) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps({"info": {"version": version}}).encode()
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    return response


def _write_state(state_dir: Path, last_check: datetime, latest_version: str) -> None:
    state_file = state_dir / "updater.json"
    state_file.write_text(
        json.dumps(
            {
                "last_check": last_check.isoformat(),
                "latest_version": latest_version,
            }
        )
    )


class TestCacheFresh:
    def test_returns_none_when_no_update(self, state_dir: Path) -> None:
        _write_state(state_dir, datetime.now(tz=timezone.utc), "0.7.0")
        with patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"):
            result = check_for_update(state_dir=state_dir)
        assert result is None

    def test_returns_cached_version_when_update_available(self, state_dir: Path) -> None:
        _write_state(state_dir, datetime.now(tz=timezone.utc), "0.8.0")
        with patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"):
            result = check_for_update(state_dir=state_dir)
        assert result == "0.8.0"

    def test_no_network_call_when_fresh(self, state_dir: Path) -> None:
        _write_state(state_dir, datetime.now(tz=timezone.utc), "0.7.0")
        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen") as mock_urlopen,
        ):
            check_for_update(state_dir=state_dir)
        mock_urlopen.assert_not_called()


class TestCacheStale:
    def test_queries_pypi_when_stale(self, state_dir: Path) -> None:
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_state(state_dir, stale_time, "0.6.0")

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.8.0")),
        ):
            result = check_for_update(state_dir=state_dir)

        assert result == "0.8.0"

    def test_updates_cache_after_pypi_query(self, state_dir: Path) -> None:
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_state(state_dir, stale_time, "0.6.0")

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.8.0")),
        ):
            check_for_update(state_dir=state_dir)

        state = json.loads((state_dir / "updater.json").read_text())
        assert state["latest_version"] == "0.8.0"
        cached_time = datetime.fromisoformat(state["last_check"])
        assert (datetime.now(tz=timezone.utc) - cached_time).total_seconds() < 5

    def test_returns_none_when_pypi_version_not_newer(self, state_dir: Path) -> None:
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_state(state_dir, stale_time, "0.6.0")

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.7.0")),
        ):
            result = check_for_update(state_dir=state_dir)

        assert result is None


class TestCacheMissingOrCorrupt:
    def test_queries_pypi_when_no_cache(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.8.0")),
        ):
            result = check_for_update(state_dir=state_dir)

        assert result == "0.8.0"

    def test_queries_pypi_when_corrupt_cache(self, state_dir: Path) -> None:
        (state_dir / "updater.json").write_text("not json{{{")

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.8.0")),
        ):
            result = check_for_update(state_dir=state_dir)

        assert result == "0.8.0"

    def test_creates_state_dir_if_missing(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "new" / "nested" / "dir"

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.8.0")),
        ):
            result = check_for_update(state_dir=nonexistent)

        assert result == "0.8.0"
        assert (nonexistent / "updater.json").exists()


class TestCachePreservesLog:
    def test_cache_update_does_not_touch_log(self, state_dir: Path) -> None:
        """Writing a cache update must preserve existing log entries in the same file."""
        (state_dir / "updater.json").write_text(
            json.dumps(
                {
                    "last_check": datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "latest_version": "0.6.0",
                    "log": [
                        {"ts": "2020-01-01T00:00:00+00:00", "level": "info", "message": "prior event"},
                    ],
                }
            )
        )

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.8.0")),
        ):
            check_for_update(state_dir=state_dir)

        state = json.loads((state_dir / "updater.json").read_text())
        assert state["latest_version"] == "0.8.0"
        assert state["log"] == [
            {"ts": "2020-01-01T00:00:00+00:00", "level": "info", "message": "prior event"},
        ]


class TestNetworkErrors:
    def test_returns_none_on_timeout(self, state_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", side_effect=TimeoutError),
        ):
            result = check_for_update(state_dir=state_dir)
        assert result is None

    def test_returns_none_on_url_error(self, state_dir: Path) -> None:
        from urllib.error import URLError

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", side_effect=URLError("no network")),
        ):
            result = check_for_update(state_dir=state_dir)
        assert result is None

    def test_returns_none_on_invalid_json_response(self, state_dir: Path) -> None:
        response = MagicMock()
        response.read.return_value = b"not json"
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(state_dir=state_dir)
        assert result is None


class TestPreReleaseFiltering:
    def test_ignores_prerelease_on_pypi(self, state_dir: Path) -> None:
        """When installed version is pre-release but PyPI stable is older, no update."""
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_state(state_dir, stale_time, "0.6.0")

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.8.0rc1"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.7.0")),
        ):
            result = check_for_update(state_dir=state_dir)

        assert result is None

    def test_suggests_stable_when_newer_than_prerelease(self, state_dir: Path) -> None:
        """When PyPI stable surpasses installed pre-release, suggest update."""
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_state(state_dir, stale_time, "0.6.0")

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.8.0rc1"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.9.0")),
        ):
            result = check_for_update(state_dir=state_dir)

        assert result == "0.9.0"


class TestFetchLatestVersion:
    def test_ignores_fresh_cache(self, state_dir: Path) -> None:
        """Fresh cache must not short-circuit: PyPI is always queried."""
        _write_state(state_dir, datetime.now(tz=timezone.utc), "0.7.0")

        with patch(
            "buvis.pybase.updater.checker.urlopen",
            return_value=_mock_pypi_response("0.9.0"),
        ) as mock_urlopen:
            result = fetch_latest_version(state_dir=state_dir)

        mock_urlopen.assert_called_once()
        assert result == "0.9.0"

    def test_writes_cache_on_success(self, state_dir: Path) -> None:
        with patch(
            "buvis.pybase.updater.checker.urlopen",
            return_value=_mock_pypi_response("0.9.0"),
        ):
            fetch_latest_version(state_dir=state_dir)

        state = json.loads((state_dir / "updater.json").read_text())
        assert state["latest_version"] == "0.9.0"
        cached_time = datetime.fromisoformat(state["last_check"])
        assert (datetime.now(tz=timezone.utc) - cached_time).total_seconds() < 5

    def test_returns_none_on_network_error(self, state_dir: Path) -> None:
        from urllib.error import URLError

        with patch(
            "buvis.pybase.updater.checker.urlopen",
            side_effect=URLError("no network"),
        ):
            result = fetch_latest_version(state_dir=state_dir)

        assert result is None

    def test_returns_none_on_invalid_json(self, state_dir: Path) -> None:
        response = MagicMock()
        response.read.return_value = b"not json"
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with patch("buvis.pybase.updater.checker.urlopen", return_value=response):
            result = fetch_latest_version(state_dir=state_dir)

        assert result is None

    def test_defaults_state_dir(self) -> None:
        """Called without state_dir, uses DEFAULT_STATE_DIR."""
        with (
            patch(
                "buvis.pybase.updater.checker.urlopen",
                return_value=_mock_pypi_response("0.9.0"),
            ),
            patch("buvis.pybase.updater.checker.write_cache") as mock_write,
        ):
            result = fetch_latest_version()

        assert result == "0.9.0"
        from buvis.pybase.updater.state import DEFAULT_STATE_DIR

        assert mock_write.call_args.args[0] == DEFAULT_STATE_DIR


class TestCustomInterval:
    def test_interval_zero_always_queries_pypi(self, state_dir: Path) -> None:
        _write_state(state_dir, datetime.now(tz=timezone.utc), "0.7.0")

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=_mock_pypi_response("0.7.0")) as mock_urlopen,
        ):
            result = check_for_update(state_dir=state_dir, interval_hours=0)

        mock_urlopen.assert_called_once()
        assert result is None

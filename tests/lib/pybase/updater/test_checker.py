"""Tests for version checking and cache management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.updater.checker import check_for_update


@pytest.fixture()
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path


def _write_cache(cache_dir: Path, last_check: datetime, latest_version: str) -> None:
    cache_file = cache_dir / ".update_cache.json"
    cache_file.write_text(
        json.dumps(
            {
                "last_check": last_check.isoformat(),
                "latest_version": latest_version,
            }
        )
    )


class TestCacheFresh:
    def test_returns_none_when_no_update(self, cache_dir: Path) -> None:
        _write_cache(cache_dir, datetime.now(tz=timezone.utc), "0.7.0")
        with patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"):
            result = check_for_update(cache_dir=cache_dir)
        assert result is None

    def test_returns_cached_version_when_update_available(self, cache_dir: Path) -> None:
        _write_cache(cache_dir, datetime.now(tz=timezone.utc), "0.8.0")
        with patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"):
            result = check_for_update(cache_dir=cache_dir)
        assert result == "0.8.0"

    def test_no_network_call_when_fresh(self, cache_dir: Path) -> None:
        _write_cache(cache_dir, datetime.now(tz=timezone.utc), "0.7.0")
        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen") as mock_urlopen,
        ):
            check_for_update(cache_dir=cache_dir)
        mock_urlopen.assert_not_called()


class TestCacheStale:
    def test_queries_pypi_when_stale(self, cache_dir: Path) -> None:
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_cache(cache_dir, stale_time, "0.6.0")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.8.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=cache_dir)

        assert result == "0.8.0"

    def test_updates_cache_after_pypi_query(self, cache_dir: Path) -> None:
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_cache(cache_dir, stale_time, "0.6.0")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.8.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            check_for_update(cache_dir=cache_dir)

        cache = json.loads((cache_dir / ".update_cache.json").read_text())
        assert cache["latest_version"] == "0.8.0"
        cached_time = datetime.fromisoformat(cache["last_check"])
        assert (datetime.now(tz=timezone.utc) - cached_time).total_seconds() < 5

    def test_returns_none_when_pypi_version_not_newer(self, cache_dir: Path) -> None:
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_cache(cache_dir, stale_time, "0.6.0")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.7.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=cache_dir)

        assert result is None


class TestCacheMissingOrCorrupt:
    def test_queries_pypi_when_no_cache(self, cache_dir: Path) -> None:
        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.8.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=cache_dir)

        assert result == "0.8.0"

    def test_queries_pypi_when_corrupt_cache(self, cache_dir: Path) -> None:
        (cache_dir / ".update_cache.json").write_text("not json{{{")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.8.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=cache_dir)

        assert result == "0.8.0"

    def test_creates_cache_dir_if_missing(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "new" / "nested" / "dir"

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.8.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=nonexistent)

        assert result == "0.8.0"
        assert (nonexistent / ".update_cache.json").exists()


class TestNetworkErrors:
    def test_returns_none_on_timeout(self, cache_dir: Path) -> None:
        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", side_effect=TimeoutError),
        ):
            result = check_for_update(cache_dir=cache_dir)
        assert result is None

    def test_returns_none_on_url_error(self, cache_dir: Path) -> None:
        from urllib.error import URLError

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", side_effect=URLError("no network")),
        ):
            result = check_for_update(cache_dir=cache_dir)
        assert result is None

    def test_returns_none_on_invalid_json_response(self, cache_dir: Path) -> None:
        response = MagicMock()
        response.read.return_value = b"not json"
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=cache_dir)
        assert result is None


class TestPreReleaseFiltering:
    def test_ignores_prerelease_on_pypi(self, cache_dir: Path) -> None:
        """When installed version is pre-release but PyPI stable is older, no update."""
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_cache(cache_dir, stale_time, "0.6.0")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.7.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.8.0rc1"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=cache_dir)

        assert result is None

    def test_suggests_stable_when_newer_than_prerelease(self, cache_dir: Path) -> None:
        """When PyPI stable surpasses installed pre-release, suggest update."""
        stale_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        _write_cache(cache_dir, stale_time, "0.6.0")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.9.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.8.0rc1"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response),
        ):
            result = check_for_update(cache_dir=cache_dir)

        assert result == "0.9.0"


class TestCustomInterval:
    def test_interval_zero_always_queries_pypi(self, cache_dir: Path) -> None:
        _write_cache(cache_dir, datetime.now(tz=timezone.utc), "0.7.0")

        response = MagicMock()
        response.read.return_value = json.dumps({"info": {"version": "0.7.0"}}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)

        with (
            patch("buvis.pybase.updater.checker.pkg_version", return_value="0.7.0"),
            patch("buvis.pybase.updater.checker.urlopen", return_value=response) as mock_urlopen,
        ):
            result = check_for_update(cache_dir=cache_dir, interval_hours=0)

        mock_urlopen.assert_called_once()
        assert result is None

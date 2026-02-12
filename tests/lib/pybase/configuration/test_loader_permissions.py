"""Tests for world-writable file detection in ConfigurationLoader."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from buvis.pybase.configuration.loader import ConfigurationLoader


class TestIsWorldWritable:
    """Tests for _is_world_writable detection."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions only")
    def test_not_world_writable(self, tmp_path: Path) -> None:
        """File with 0o644 is not world-writable."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")
        config.chmod(0o644)

        assert ConfigurationLoader._is_world_writable(config) is False

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions only")
    def test_world_writable_0o666(self, tmp_path: Path) -> None:
        """File with 0o666 is world-writable."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")
        config.chmod(0o666)

        assert ConfigurationLoader._is_world_writable(config) is True

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions only")
    def test_world_writable_0o777(self, tmp_path: Path) -> None:
        """File with 0o777 is world-writable."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")
        config.chmod(0o777)

        assert ConfigurationLoader._is_world_writable(config) is True

    def test_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        """Non-existent file returns False."""
        missing = tmp_path / "missing.yaml"

        assert ConfigurationLoader._is_world_writable(missing) is False

    def test_oserror_returns_false(self, tmp_path: Path) -> None:
        """OSError during stat returns False."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")

        with patch.object(Path, "stat", side_effect=OSError("Access denied")):
            assert ConfigurationLoader._is_world_writable(config) is False


class TestWorldWritableWarning:
    """Tests for world-writable warning in load_yaml."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions only")
    def test_warns_on_world_writable_file(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """World-writable config file triggers warning."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")
        config.chmod(0o666)

        with caplog.at_level("WARNING"):
            ConfigurationLoader.load_yaml(config)

        assert "world-writable" in caplog.text
        assert str(config) in caplog.text

    def test_no_warning_on_normal_file(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Normal file does not trigger warning."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")

        with caplog.at_level("WARNING"):
            ConfigurationLoader.load_yaml(config)

        assert "world-writable" not in caplog.text

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions only")
    def test_still_loads_world_writable_file(self, tmp_path: Path) -> None:
        """World-writable file is still loaded (warn only, not reject)."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")
        config.chmod(0o666)

        result = ConfigurationLoader.load_yaml(config)

        assert result == {"key": "value"}

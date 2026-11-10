"""Tests for configuration directory trust and world-writable file warnings."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from buvis.pybase.configuration.exceptions import ConfigurationError
from buvis.pybase.configuration.loader import ConfigurationLoader


@pytest.mark.skipif(os.name != "posix", reason="Requires Unix permissions and ownership")
class TestParentDirectoryTrust:
    @pytest.mark.parametrize("link", ["none", "directory", "file"])
    def test_rejects_before_reading(self, tmp_path: Path, link: str) -> None:
        directory = tmp_path / "unsafe"
        directory.mkdir()
        config = directory / "config.yaml"
        config.write_text("key: value\n")
        config.chmod(0o644)
        directory.chmod(0o777)
        candidate = config
        if link == "directory":
            alias = tmp_path / "alias"
            alias.symlink_to(directory, target_is_directory=True)
            candidate = alias / config.name
        elif link == "file":
            candidate = tmp_path / "alias.yaml"
            candidate.symlink_to(config)

        with (
            patch.object(Path, "read_text", side_effect=AssertionError("Unsafe config was read")) as read,
            pytest.raises(ConfigurationError) as error,
        ):
            ConfigurationLoader.load_yaml(candidate)

        read.assert_not_called()
        assert str(candidate) in str(error.value)
        assert str(directory.resolve()) in str(error.value)
        assert "world-writable" in str(error.value)
        assert "chmod o-w" in str(error.value)

    @pytest.mark.parametrize("mode", [0o700, 0o755, 0o770, 0o1777])
    @pytest.mark.parametrize("symlink", [False, True])
    def test_safe_directory_loads(self, tmp_path: Path, mode: int, symlink: bool) -> None:
        directory = tmp_path / "safe"
        directory.mkdir()
        config = directory / "config.yaml"
        config.write_text("key: value\n")
        directory.chmod(mode)
        candidate = config
        if symlink:
            alias = tmp_path / "alias"
            alias.symlink_to(directory, target_is_directory=True)
            candidate = alias / config.name

        assert ConfigurationLoader.load_yaml(candidate) == {"key": "value"}

    @pytest.mark.parametrize("directory_uid", [0, 1000, 2000])
    @pytest.mark.parametrize("file_uid", [0, 1000, 2000])
    def test_sticky_directory_ownership(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory_uid: int, file_uid: int
    ) -> None:
        directory = tmp_path.resolve()
        config = directory / "config.yaml"
        config.write_text("key: value\n")
        config.chmod(0o644)
        directory.chmod(0o1777)
        original_stat = Path.stat

        def stat_with_owner(path: Path, *, follow_symlinks: bool = True) -> os.stat_result:
            result = original_stat(path, follow_symlinks=follow_symlinks)
            if path in (directory, config):
                fields = list(result)
                fields[4] = directory_uid if path == directory else file_uid
                return os.stat_result(fields)
            return result

        monkeypatch.setattr(Path, "stat", stat_with_owner)
        monkeypatch.setattr(os, "geteuid", lambda: 1000)
        # Trust must use the effective identity, not the real identity.
        monkeypatch.setattr(os, "getuid", lambda: 2000)

        if directory_uid == 2000 or file_uid == 2000:
            with (
                patch.object(Path, "read_text", side_effect=AssertionError("Unsafe config was read")) as read,
                pytest.raises(ConfigurationError, match="chmod o-w"),
            ):
                ConfigurationLoader.load_yaml(config)
            read.assert_not_called()
        else:
            assert ConfigurationLoader.load_yaml(config) == {"key": "value"}

    def test_windows_skips_unix_directory_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")
        tmp_path.chmod(0o777)
        with monkeypatch.context() as platform:
            platform.setattr(os, "name", "nt")
            platform.delattr(os, "geteuid")
            assert ConfigurationLoader.load_yaml(config) == {"key": "value"}


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

    def test_always_false_on_windows(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Windows, _is_world_writable always returns False."""
        config = tmp_path / "config.yaml"
        config.write_text("key: value\n")

        monkeypatch.setattr("os.name", "nt")
        assert ConfigurationLoader._is_world_writable(config) is False

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

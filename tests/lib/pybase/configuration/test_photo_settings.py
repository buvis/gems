"""Tests for PhotoSettings example configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from buvis.pybase.configuration.examples import PhotoSettings
from buvis.pybase.configuration.settings import GlobalSettings
from pydantic import ValidationError


class TestPhotoSettingsDefaults:
    def test_library_path_defaults_to_pictures(self) -> None:
        settings = PhotoSettings()

        assert settings.library_path == Path.home() / "Pictures"

    def test_thumbnail_size_defaults_to_256(self) -> None:
        settings = PhotoSettings()

        assert settings.thumbnail_size == 256


class TestPhotoSettingsInheritance:
    def test_inherits_global_fields(self) -> None:
        global_settings = GlobalSettings()
        settings = PhotoSettings()

        assert settings.debug is global_settings.debug
        assert settings.log_level == global_settings.log_level
        assert settings.output_format == global_settings.output_format


class TestPhotoSettingsEnvOverride:
    def test_library_path_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        custom_path = "/tmp/photos"
        monkeypatch.setenv("BUVIS_PHOTO_LIBRARY_PATH", custom_path)

        settings = PhotoSettings()

        assert settings.library_path == Path(custom_path)

    def test_thumbnail_size_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_PHOTO_THUMBNAIL_SIZE", "512")

        settings = PhotoSettings()

        assert settings.thumbnail_size == 512


class TestPhotoSettingsImmutability:
    def test_fields_are_immutable(self) -> None:
        settings = PhotoSettings()

        with pytest.raises(ValidationError):
            settings.library_path = Path("/new/path")

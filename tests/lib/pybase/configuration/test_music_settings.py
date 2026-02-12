"""Tests for MusicSettings example configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from buvis.pybase.configuration.examples import MusicSettings
from buvis.pybase.configuration.settings import GlobalSettings


class TestMusicSettingsDefaults:
    def test_library_path_defaults_to_music(self) -> None:
        settings = MusicSettings()

        assert settings.library_path == Path.home() / "Music"

    def test_formats_default(self) -> None:
        settings = MusicSettings()

        assert settings.formats == ["mp3", "flac", "wav"]


class TestMusicSettingsInheritance:
    def test_inherits_global_fields(self) -> None:
        global_settings = GlobalSettings()
        settings = MusicSettings()

        assert settings.debug is global_settings.debug
        assert settings.log_level == global_settings.log_level
        assert settings.output_format == global_settings.output_format


class TestMusicSettingsEnvOverride:
    def test_library_path_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        custom_path = "/tmp/music"
        monkeypatch.setenv("BUVIS_MUSIC_LIBRARY_PATH", custom_path)

        settings = MusicSettings()

        assert settings.library_path == Path(custom_path)

    def test_formats_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_MUSIC_FORMATS", '["ogg","aac"]')

        settings = MusicSettings()

        assert settings.formats == ["ogg", "aac"]


class TestMusicSettingsImmutability:
    def test_fields_are_immutable(self) -> None:
        settings = MusicSettings()

        with pytest.raises(ValidationError):
            settings.library_path = Path("/new/path")

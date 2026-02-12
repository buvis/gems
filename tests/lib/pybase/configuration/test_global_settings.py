"""Tests for GlobalSettings class."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from buvis.pybase.configuration.settings import GlobalSettings


class TestGlobalSettingsDefaults:
    def test_debug_defaults_to_false(self) -> None:
        settings = GlobalSettings()

        assert settings.debug is False

    def test_log_level_defaults_to_info(self) -> None:
        settings = GlobalSettings()

        assert settings.log_level == "INFO"

    def test_output_format_defaults_to_text(self) -> None:
        settings = GlobalSettings()

        assert settings.output_format == "text"


class TestGlobalSettingsValidation:
    def test_invalid_log_level_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            GlobalSettings(log_level="INVALID")

    def test_invalid_output_format_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            GlobalSettings(output_format="xml")


class TestGlobalSettingsEnvLoading:
    def test_debug_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_DEBUG", "true")

        settings = GlobalSettings()

        assert settings.debug is True

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_LOG_LEVEL", "DEBUG")

        settings = GlobalSettings()

        assert settings.log_level == "DEBUG"


class TestGlobalSettingsImmutability:
    def test_mutation_raises_error(self) -> None:
        settings = GlobalSettings()

        with pytest.raises(ValidationError):
            settings.debug = True


class TestGlobalSettingsExtraForbid:
    def test_unknown_field_raises_error(self) -> None:
        with pytest.raises(ValidationError):
            GlobalSettings(unknown_field="value")

"""Tests for settings immutability enforcement."""

from __future__ import annotations

import pytest
from buvis.pybase.configuration.settings import GlobalSettings, ToolSettings
from pydantic import ValidationError


class TestGlobalSettingsImmutability:
    """Tests for GlobalSettings frozen behavior."""

    def test_debug_immutable(self) -> None:
        """debug field cannot be mutated."""
        settings = GlobalSettings()

        with pytest.raises(ValidationError):
            settings.debug = True

    def test_log_level_immutable(self) -> None:
        """log_level field cannot be mutated."""
        settings = GlobalSettings()

        with pytest.raises(ValidationError):
            settings.log_level = "DEBUG"

    def test_output_format_immutable(self) -> None:
        """output_format field cannot be mutated."""
        settings = GlobalSettings()

        with pytest.raises(ValidationError):
            settings.output_format = "json"


class TestToolSettingsImmutability:
    """Tests for ToolSettings frozen behavior."""

    def test_enabled_immutable(self) -> None:
        """enabled field cannot be mutated."""
        tool = ToolSettings()

        with pytest.raises(ValidationError):
            tool.enabled = False


class TestImmutabilityErrorMessages:
    """Tests for error message content on mutation attempts."""

    def test_error_mentions_frozen(self) -> None:
        """Mutation error mentions frozen or immutable."""
        settings = GlobalSettings()

        with pytest.raises(ValidationError) as exc_info:
            settings.debug = True

        error_str = str(exc_info.value).lower()
        assert "frozen" in error_str or "immutable" in error_str

    def test_error_mentions_field_name(self) -> None:
        """Mutation error mentions the field name."""
        settings = GlobalSettings()

        with pytest.raises(ValidationError) as exc_info:
            settings.log_level = "ERROR"

        assert "log_level" in str(exc_info.value)


class TestImmutabilityAfterResolve:
    """Tests for immutability of settings returned from ConfigResolver."""

    def test_resolved_settings_immutable(self) -> None:
        """Settings from resolve() cannot be mutated."""
        from buvis.pybase.configuration.resolver import ConfigResolver

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings)

        with pytest.raises(ValidationError):
            settings.debug = True

    def test_resolved_settings_all_fields_immutable(self) -> None:
        """All fields of resolved settings are immutable."""
        from buvis.pybase.configuration.resolver import ConfigResolver

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings)

        for field in GlobalSettings.model_fields:
            with pytest.raises(ValidationError):
                setattr(settings, field, "invalid")

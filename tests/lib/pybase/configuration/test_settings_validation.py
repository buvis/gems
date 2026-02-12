"""Tests for settings validation at instantiation time.

These tests verify Pydantic validates settings immediately at instantiation,
not at use time. This ensures configuration errors are caught early.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from buvis.pybase.configuration.settings import GlobalSettings, ToolSettings


class TestLogLevelValidation:
    def test_invalid_log_level_raises_at_instantiation(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            GlobalSettings(log_level="INVALID")

        assert "log_level" in str(exc_info.value)

    def test_lowercase_log_level_fails(self) -> None:
        with pytest.raises(ValidationError):
            GlobalSettings(log_level="info")


class TestOutputFormatValidation:
    def test_invalid_output_format_raises(self) -> None:
        with pytest.raises(ValidationError):
            GlobalSettings(output_format="xml")

    def test_output_format_error_message(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            GlobalSettings(output_format="html")

        assert "output_format" in str(exc_info.value)


class TestValidSettingsInstantiation:
    def test_default_values_valid(self) -> None:
        settings = GlobalSettings()

        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.output_format == "text"

    @pytest.mark.parametrize(
        "log_level",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    def test_all_valid_log_levels(self, log_level: str) -> None:
        settings = GlobalSettings(log_level=log_level)

        assert settings.log_level == log_level

    @pytest.mark.parametrize("output_format", ["text", "json", "yaml"])
    def test_all_valid_output_formats(self, output_format: str) -> None:
        settings = GlobalSettings(output_format=output_format)

        assert settings.output_format == output_format

    @pytest.mark.parametrize("debug", [True, False])
    def test_valid_debug_boolean(self, debug: bool) -> None:
        settings = GlobalSettings(debug=debug)

        assert settings.debug is debug


class TestToolSettingsValidation:
    def test_tool_settings_enabled_requires_bool(self) -> None:
        with pytest.raises(ValidationError):
            ToolSettings(enabled=[1, 2, 3])

    def test_validation_error_contains_field_path(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ToolSettings(enabled="invalid")

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("enabled",) for err in errors)


class TestValidationErrorDetails:
    def test_log_level_error_shows_allowed_values(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            GlobalSettings(log_level="TRACE")

        error_str = str(exc_info.value)
        assert "DEBUG" in error_str or "literal" in error_str.lower()

    def test_error_provides_structured_info(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            GlobalSettings(output_format="csv")

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "loc" in errors[0]
        assert "type" in errors[0]

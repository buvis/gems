"""Tests for sensitive field audit logging in ConfigResolver."""

from __future__ import annotations

import logging
from typing import Literal

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict


class SensitiveTestSettings(BaseSettings):
    """Test settings with sensitive and non-sensitive fields."""

    model_config = SettingsConfigDict(
        env_prefix="TEST_",
        frozen=True,
        extra="forbid",
    )

    # Non-sensitive fields
    debug: bool = False
    log_level: Literal["DEBUG", "INFO"] = "INFO"

    # Sensitive fields (detected by name pattern)
    api_key: str = "default-key"
    database_password: str = "default-pass"
    auth_token: str = "default-token"
    client_secret: str = "default-secret"


class TestSensitiveFieldLogging:
    """Tests for differentiated log levels based on field sensitivity."""

    def test_sensitive_field_logged_at_info(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sensitive fields are logged at INFO level."""
        from buvis.pybase.configuration.resolver import ConfigResolver

        monkeypatch.setenv("TEST_API_KEY", "secret-key-12345")

        with caplog.at_level(logging.DEBUG):
            resolver = ConfigResolver()
            resolver.resolve(SensitiveTestSettings)

        # api_key should be logged at INFO
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("api_key" in r.message for r in info_records)

    def test_non_sensitive_field_logged_at_debug(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-sensitive fields are logged at DEBUG level only."""
        from buvis.pybase.configuration.resolver import ConfigResolver

        monkeypatch.setenv("TEST_DEBUG", "true")

        with caplog.at_level(logging.DEBUG):
            resolver = ConfigResolver()
            resolver.resolve(SensitiveTestSettings)

        # debug field should only appear in DEBUG records
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]

        assert any("debug" in r.message for r in debug_records)
        assert not any("'debug'" in r.message for r in info_records)

    def test_no_actual_values_in_logs(self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
        """Actual secret values never appear in log messages."""
        from buvis.pybase.configuration.resolver import ConfigResolver

        secret_value = "super-secret-test-value-xyz789"
        monkeypatch.setenv("TEST_API_KEY", secret_value)

        with caplog.at_level(logging.DEBUG):
            resolver = ConfigResolver()
            resolver.resolve(SensitiveTestSettings)

        # Secret value must never appear in any log message
        full_log = caplog.text
        assert secret_value not in full_log

    def test_multiple_sensitive_fields_all_at_info(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All sensitive fields logged at INFO regardless of source."""
        from buvis.pybase.configuration.resolver import ConfigResolver

        monkeypatch.setenv("TEST_API_KEY", "key1")
        monkeypatch.setenv("TEST_DATABASE_PASSWORD", "pass1")
        monkeypatch.setenv("TEST_AUTH_TOKEN", "tok1")

        with caplog.at_level(logging.DEBUG):
            resolver = ConfigResolver()
            resolver.resolve(SensitiveTestSettings)

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        info_text = " ".join(r.message for r in info_records)

        assert "api_key" in info_text
        assert "database_password" in info_text
        assert "auth_token" in info_text

    def test_log_contains_source_type(self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
        """Log messages include source type (ENV, CLI, etc.)."""
        from buvis.pybase.configuration.resolver import ConfigResolver

        monkeypatch.setenv("TEST_API_KEY", "from-env")

        with caplog.at_level(logging.DEBUG):
            resolver = ConfigResolver()
            resolver.resolve(SensitiveTestSettings)

        # Should mention "env" as source
        assert "env" in caplog.text.lower()

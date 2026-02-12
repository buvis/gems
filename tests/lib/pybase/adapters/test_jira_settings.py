"""Tests for Jira adapter settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from buvis.pybase.adapters.jira.settings import JiraFieldMappings, JiraSettings


@pytest.fixture
def base_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Set required Jira environment values."""
    monkeypatch.setenv("BUVIS_JIRA_SERVER", "https://jira.example.com")
    monkeypatch.setenv("BUVIS_JIRA_TOKEN", "test-token")
    return monkeypatch


class TestJiraSettings:
    """Ensure JiraSettings loads configuration from the environment."""

    def test_loads_from_env_vars(self, base_env: pytest.MonkeyPatch) -> None:
        """Server, token, and proxy values come directly from env vars."""
        base_env.setenv("BUVIS_JIRA_PROXY", "http://proxy.local:8080")
        settings = JiraSettings()

        assert settings.server == "https://jira.example.com"
        assert settings.token.get_secret_value() == "test-token"
        assert settings.proxy == "http://proxy.local:8080"

    def test_token_masked_in_repr(self, base_env: pytest.MonkeyPatch) -> None:
        """Token is masked in repr to prevent leakage."""
        settings = JiraSettings()

        assert "test-token" not in repr(settings)

    @pytest.mark.parametrize("missing_var", ["BUVIS_JIRA_SERVER", "BUVIS_JIRA_TOKEN"])
    def test_missing_required_fields_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch, missing_var: str
    ) -> None:
        """Omitting a required field from the environment triggers ValidationError."""
        monkeypatch.setenv("BUVIS_JIRA_SERVER", "https://jira.example.com")
        monkeypatch.setenv("BUVIS_JIRA_TOKEN", "test-token")
        monkeypatch.delenv(missing_var, raising=False)

        with pytest.raises(ValidationError):
            JiraSettings()

    def test_default_field_mappings(self, base_env: pytest.MonkeyPatch) -> None:
        """Field mappings default to the expected custom field keys."""
        settings = JiraSettings()

        assert settings.field_mappings == JiraFieldMappings()

    def test_nested_delimiter_parses_overrides(self, base_env: pytest.MonkeyPatch) -> None:
        """Nested field mapping overrides load via the nested delimiter."""
        base_env.setenv("BUVIS_JIRA_FIELD_MAPPINGS__TICKET", "custom_ticket")
        base_env.setenv("BUVIS_JIRA_FIELD_MAPPINGS__REGION", "custom_region")
        settings = JiraSettings()

        assert settings.field_mappings.ticket == "custom_ticket"
        assert settings.field_mappings.region == "custom_region"

    def test_proxy_is_optional(self, base_env: pytest.MonkeyPatch) -> None:
        """Proxy defaults to None when not configured."""
        settings = JiraSettings()

        assert settings.proxy is None


class TestJiraFieldMappings:
    """Test JiraFieldMappings model."""

    def test_frozen_prevents_mutation(self) -> None:
        """Attempting to modify a frozen field raises ValidationError."""
        mappings = JiraFieldMappings()
        with pytest.raises(ValidationError):
            mappings.ticket = "new_value"

"""Jira adapter configuration settings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["JiraFieldMappings", "JiraSettings"]


class JiraFieldMappings(BaseModel):
    """Custom field keys used by Jira settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticket: str = "customfield_11502"
    team: str = "customfield_10501"
    feature: str = "customfield_10001"
    region: str = "customfield_12900"


class JiraSettings(BaseSettings):
    """Environment-driven Jira configuration values."""

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_JIRA_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    server: str
    token: SecretStr
    proxy: str | None = None
    field_mappings: JiraFieldMappings = JiraFieldMappings()

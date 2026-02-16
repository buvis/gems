from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class OutlookctlSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_OUTLOOKCTL_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    default_timeblock_duration: int = 25

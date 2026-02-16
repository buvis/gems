from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class ReaderctlSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_READERCTL_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    token_file: str = "~/.config/scripts/readwise-token"

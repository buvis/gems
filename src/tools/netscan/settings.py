from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class NetscanSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_NETSCAN_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    interface: str = "en0"
    ssh_port: int = 22

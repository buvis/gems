from __future__ import annotations

from typing import ClassVar

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class BackupSettings(GlobalSettings):
    # Validated by BackupConfig after the runtime settings have been resolved.
    config_deferred_keys: ClassVar[frozenset[str]] = frozenset({"instances", "excludes"})

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_BACKUP_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

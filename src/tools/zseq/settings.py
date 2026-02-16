from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class ZseqSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_ZSEQ_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    path_dir: str = "/Volumes/photography/photography/src/2024"
    is_reporting_misnamed: bool = False

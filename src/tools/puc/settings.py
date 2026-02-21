from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class PucSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_PUC_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    strip_keep_tags: list[str] = Field(
        default=[
            "DateTimeOriginal",
            "CreateDate",
            "ModifyDate",
            "Copyright",
            "XMP-dc:Rights",
            "IPTC:CopyrightNotice",
        ]
    )

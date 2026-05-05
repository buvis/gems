from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict

from bim.commands.doc.shared.settings_models import DocSettings


class BimSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_BIM_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    path_zettelkasten: str = "~/bim/zettelkasten/"
    path_archive: str = "~/bim/reference/40-archives/"
    doc: DocSettings | None = None

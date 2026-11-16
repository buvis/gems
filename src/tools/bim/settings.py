from __future__ import annotations

from buvis.pybase.configuration import GlobalSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from bim.commands.doc.shared.settings_models import DocSettings
from bim.commands.tx.shared.settings import TxSettings


class BimSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_BIM_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    path_zettelkasten: str = "~/bim/notes/"
    path_archive: str = "~/Documents/reference/40-archives/"
    path_projects: str = "~/Documents/reference/10-projects/"
    path_daily: str = "~/bim/notes/calendar/daily/"
    path_articles: str = "~/Documents/reference/40-archives/articles/"
    doc: DocSettings | None = None
    tiromex_folder: str = "tiromex"
    tx: TxSettings = Field(default_factory=TxSettings)

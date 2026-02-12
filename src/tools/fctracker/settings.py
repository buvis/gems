from buvis.pybase.configuration import GlobalSettings
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict


class LocalCurrencyConfig(BaseModel):
    code: str = "CZK"
    symbol: str = "Kč"
    precision: int = 2


class ForeignCurrencyConfig(BaseModel):
    symbol: str = ""
    precision: int = 2


class FctrackerSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_FCTRACKER_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    transactions_dir: str = ""
    local_currency: LocalCurrencyConfig = LocalCurrencyConfig()
    foreign_currencies: dict[str, ForeignCurrencyConfig] = {}  # noqa: RUF012 - pydantic field

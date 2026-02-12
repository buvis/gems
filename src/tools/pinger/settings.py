from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class PingerSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_PINGER_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    host: str = "127.0.0.1"
    wait_timeout: int = 600

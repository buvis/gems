from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class HelloWorldSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_HELLO_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    font: str = "doom"
    text: str = "World"

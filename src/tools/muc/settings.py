from buvis.pybase.configuration import GlobalSettings
from pydantic_settings import SettingsConfigDict


class MucSettings(GlobalSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUVIS_MUC_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )

    # Limit command settings
    limit_flac_bitrate: int = 1411000
    limit_flac_bit_depth: int = 16
    limit_flac_sampling_rate: int = 44100

    # Tidy command settings
    tidy_junk_extensions: list[str] = [  # noqa: RUF012 - pydantic field
        ".cue",
        ".db",
        ".jpg",
        ".jpeg",
        ".lrc",
        ".m3u",
        ".m3u8",
        ".md",
        ".nfo",
        ".png",
        ".sfv",
        ".txt",
        ".url",
    ]

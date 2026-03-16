"""Configuration management with precedence: CLI > ENV > YAML > Defaults.

Usage::

    from buvis.pybase.configuration import get_settings, buvis_options

    @click.command()
    @buvis_options
    @click.pass_context
    def main(ctx):
        settings = get_settings(ctx)
        if settings.debug:
            ...

Precedence (highest to lowest):
    1. CLI arguments (--debug, --log-level, etc.)
    2. Environment variables (BUVIS_* prefix)
    3. YAML config file (~/.config/buvis/config.yaml)
    4. Model defaults
"""

from __future__ import annotations

from .click_integration import apply_generated_options, buvis_options, generate_click_options, get_settings
from .config_writer import ConfigWriter
from .exceptions import (
    ConfigurationError,
    ConfigurationKeyNotFoundError,
    MissingEnvVarError,
)
from .loader import ConfigurationLoader, get_config_dirs
from .resolver import ConfigResolver, ConfigSource
from .settings import GlobalSettings, SafeLoggingMixin, SecureSettingsMixin, ToolSettings
from .validators import (
    MAX_JSON_ENV_SIZE,
    MAX_NESTING_DEPTH,
    get_model_depth,
    is_sensitive_field,
    validate_json_env_size,
    validate_nesting_depth,
)

__all__ = [
    "MAX_JSON_ENV_SIZE",
    "MAX_NESTING_DEPTH",
    "ConfigResolver",
    "ConfigSource",
    "ConfigWriter",
    "ConfigurationError",
    "ConfigurationKeyNotFoundError",
    "ConfigurationLoader",
    "GlobalSettings",
    "MissingEnvVarError",
    "SafeLoggingMixin",
    "SecureSettingsMixin",
    "ToolSettings",
    "apply_generated_options",
    "buvis_options",
    "generate_click_options",
    "get_config_dirs",
    "get_model_depth",
    "get_settings",
    "is_sensitive_field",
    "validate_json_env_size",
    "validate_nesting_depth",
]

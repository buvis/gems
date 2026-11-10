"""Resolve Buvis settings using the configuration loader and optional CLI overrides.

This module provides ConfigResolver for unified configuration loading with
precedence handling across multiple sources (CLI, ENV, YAML, defaults).

Example:
    Basic usage::

        from buvis.pybase.configuration import ConfigResolver, GlobalSettings

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings)
        print(settings.debug)

    Error handling::

        from buvis.pybase.configuration import ConfigResolver, ConfigurationError
        import sys

        try:
            resolver = ConfigResolver()
            settings = resolver.resolve(GlobalSettings)
        except ConfigurationError as e:
            print(f"Config error: {e}")
            sys.exit(1)
"""

from __future__ import annotations

import logging
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsError

from .exceptions import ConfigurationError, MissingEnvVarError
from .loader import ConfigurationLoader, _parse_yaml_mapping, _split_directive
from .validators import is_sensitive_field

__all__ = ["ConfigResolver", "ConfigSource"]


class ConfigSource(Enum):
    """Source from which a configuration value was obtained."""

    DEFAULT = "default"
    YAML = "yaml"
    ENV = "env"
    CLI = "cli"


logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseSettings)


def _load_yaml_config(file_path: Path | None = None) -> dict[str, Any]:
    """Load YAML config, return empty dict if not found.

    Args:
        file_path: Path to YAML file. If None, uses BUVIS_CONFIG_FILE env var
            or defaults to ~/.config/buvis/config.yaml.

    Returns:
        Parsed YAML as dict, or empty dict if file doesn't exist.

    Raises:
        ConfigurationError: If YAML syntax is invalid.
    """
    if file_path is None:
        default = Path.home() / ".config" / "buvis" / "config.yaml"
        file_path = Path(os.getenv("BUVIS_CONFIG_FILE", str(default)))

    if not file_path.exists():
        return {}

    try:
        return _parse_yaml_mapping(file_path.read_text(encoding="utf-8"), file_path)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line_num = mark.line + 1 if mark else "unknown"
        raise ConfigurationError(f"YAML syntax error in {file_path}:{line_num}: {e}") from e
    except PermissionError:
        logger.warning("Permission denied reading %s, skipping", file_path)
        return {}


def _extract_tool_name(env_prefix: str) -> str | None:
    """Extract tool name from env prefix like BUVIS_FOO_ -> foo."""
    match = re.match(r"^BUVIS_([A-Z][A-Z0-9_]*)_$", env_prefix)
    if not match:
        return None
    return match.group(1).lower()


def _format_validation_errors(error: ValidationError, sources: dict[tuple[str, ...], list[Path]] | None = None) -> str:
    """Format Pydantic validation errors into user-friendly message.

    Masks error details for sensitive fields (password, token, etc.)
    to prevent secret leakage in error messages.

    Args:
        error: Pydantic ValidationError to format.

    Returns:
        Formatted error message with field paths and descriptions.
    """
    lines = []
    for err in error.errors():
        field_path = ".".join(str(loc) for loc in err["loc"])
        if is_sensitive_field(field_path):
            msg = "invalid value (hidden)"
        else:
            msg = err["msg"]
        field = tuple(str(loc) for loc in err["loc"])
        source = None
        while field and source is None:
            source = (sources or {}).get(field)
            field = field[:-1]
        location = f" ({', '.join(map(str, source))})" if source else ""
        lines.append(f"  {field_path}{location}: {msg}")
    return "Configuration validation failed:\n" + "\n".join(lines)


def _record_yaml_sources(
    layer: dict[str, Any],
    path: Path,
    sources: dict[tuple[str, ...], list[Path]],
    prefix: tuple[str, ...] = (),
) -> None:
    """Retain the source of nested values when a later layer merges siblings."""
    for key, value in layer.items():
        base, directive = _split_directive(key)
        field = (*prefix, base)
        if directive:
            # A list error may originate in any contributing layer.
            sources[field] = list(dict.fromkeys([*sources.get(field, []), path]))
            continue
        if isinstance(value, dict):
            _record_yaml_sources(value, path, sources, field)
        else:
            # A replacement also discards provenance of any former children.
            for previous in list(sources):
                if previous[: len(field)] == field:
                    del sources[previous]
        sources[field] = [path]


class ConfigResolver:
    """Unified configuration loader with precedence handling.

    Orchestrates config loading from multiple sources:

    - YAML files (via ConfigurationLoader discovery)
    - Environment variables (via Pydantic, BUVIS_* prefix)
    - CLI overrides (passed to resolve())

    Precedence (highest to lowest):

    1. CLI overrides
    2. Environment variables (BUVIS_* prefix)
    3. YAML config files
    4. Model defaults

    Example:
        Basic usage::

            resolver = ConfigResolver()
            settings = resolver.resolve(GlobalSettings)

        With CLI overrides from Click::

            @click.command()
            @click.option('--debug', is_flag=True)
            def main(debug):
                resolver = ConfigResolver()
                settings = resolver.resolve(
                    GlobalSettings,
                    cli_overrides={"debug": debug} if debug else None,
                )

        Custom config directory::

            settings = resolver.resolve(GlobalSettings, config_dir="/etc/buvis")

    Note:
        Settings are immutable after resolve(). Instances are frozen. The tool
        name is inferred from ``settings_class.model_config['env_prefix']``
        following the pattern ``BUVIS_{TOOL}_`` -> ``"tool"``; you no longer
        pass ``tool_name`` manually.
    """

    def __init__(self) -> None:
        """Create a resolver."""
        self.loader = ConfigurationLoader()
        self._sources: dict[str, ConfigSource] = {}
        self._yaml_sources: dict[tuple[str, ...], list[Path]] = {}
        logger.debug("ConfigResolver initialized")

    def _load_yaml(
        self,
        tool_name: str | None,
        config_dir: str | None,
        config_path: Path | None,
        *,
        include_cwd: bool = True,
    ) -> dict[str, Any]:
        """Load YAML config from explicit path or discovered files."""
        if config_dir is not None:
            logger.debug("Using config_dir override: %s", config_dir)
        self._yaml_sources.clear()
        discovered_files = (
            [config_path]
            if config_path is not None
            else self.loader.find_config_files_ranked(tool_name, config_dir=config_dir, include_cwd=include_cwd)
        )
        merged: dict[str, Any] = {}
        for path in discovered_files:
            try:
                layer = _load_yaml_config(path) if config_path is not None else self.loader.load_yaml(path)
                merged = layer if config_path is not None else self.loader.merge_configs(merged, layer)
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                location = f"{path}:{mark.line + 1}" if mark else str(path)
                problem = getattr(exc, "problem", None) or str(exc)
                raise ConfigurationError(f"YAML syntax error in {location}: {problem}") from exc
            except (MissingEnvVarError, ConfigurationError) as exc:
                if str(exc).startswith(f"{path}:"):
                    raise
                raise ConfigurationError(f"{path}: {exc}") from exc
            _record_yaml_sources(layer, path, self._yaml_sources)
        return merged

    @staticmethod
    def _merge_overrides(
        settings_class: type[T],
        base_settings: T,
        yaml_config: dict[str, Any],
        cli_overrides: dict[str, Any] | None,
    ) -> T:
        """Merge YAML and CLI overrides onto base settings."""
        merged: dict[str, Any] = {}
        for key, value in yaml_config.items():
            if hasattr(base_settings, key):
                field_value = getattr(base_settings, key)
                default = settings_class.model_fields.get(key)
                if default and field_value == default.default:
                    merged[key] = value
        if cli_overrides:
            for key, value in cli_overrides.items():
                if value is not None:
                    merged[key] = value
        if merged:
            return settings_class.model_validate(base_settings.model_dump() | merged)
        return base_settings

    def _track_sources(
        self,
        settings_class: type[T],
        env_prefix: str,
        yaml_config: dict[str, Any],
        cli_overrides: dict[str, Any] | None,
    ) -> None:
        """Record which source provided each field value."""
        env_keys = {k.removeprefix(env_prefix).lower() for k in os.environ if k.startswith(env_prefix)}
        self._sources.clear()
        for field in settings_class.model_fields:
            if cli_overrides and cli_overrides.get(field) is not None:
                self._sources[field] = ConfigSource.CLI
            elif field in env_keys:
                self._sources[field] = ConfigSource.ENV
            elif field in yaml_config:
                self._sources[field] = ConfigSource.YAML
            else:
                self._sources[field] = ConfigSource.DEFAULT

    def resolve(
        self,
        settings_class: type[T],
        config_dir: str | None = None,
        config_path: Path | None = None,
        cli_overrides: dict[str, Any] | None = None,
    ) -> T:
        """Instantiate a settings class with precedence: CLI > ENV > YAML > Defaults."""
        env_prefix = settings_class.model_config.get("env_prefix", "BUVIS_")
        tool_name = _extract_tool_name(env_prefix)

        yaml_config = self._load_yaml(
            tool_name, config_dir, config_path, include_cwd=getattr(settings_class, "config_include_cwd", True)
        )
        logger.debug("Loaded YAML config: %s", yaml_config)

        try:
            base_settings = settings_class()
        except ValidationError as exc:
            raise ConfigurationError(_format_validation_errors(exc)) from exc
        except SettingsError as exc:
            raise ConfigurationError(str(exc)) from exc

        try:
            final_settings = self._merge_overrides(settings_class, base_settings, yaml_config, cli_overrides)
            self._track_sources(settings_class, env_prefix, yaml_config, cli_overrides)
            self._log_sources()
            return final_settings
        except ValidationError as e:
            raise ConfigurationError(_format_validation_errors(e, self._yaml_sources)) from e

    def _log_sources(self) -> None:
        """Log config field sources. Sensitive fields use INFO, others DEBUG.

        Never logs actual values - only field names and source types.
        """
        for field, source in self._sources.items():
            if is_sensitive_field(field):
                logger.info("Security config '%s' loaded from %s", field, source.value)
            else:
                logger.debug("Config '%s' from %s", field, source.value)

    @property
    def sources(self) -> dict[str, ConfigSource]:
        """Get copy of source tracking dict."""
        return self._sources.copy()

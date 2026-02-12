"""Tests for configuration edge cases per PRD-00007."""

from __future__ import annotations

from pathlib import Path

import pytest
from buvis.pybase.configuration.resolver import ConfigResolver
from buvis.pybase.configuration.settings import GlobalSettings


class TestEnvEmptyString:
    """ENV empty string behavior: empty string is a value, not missing."""

    def test_env_empty_string_for_output_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string ENV is used, not default."""
        # output_format accepts string, set to empty
        monkeypatch.setenv("BUVIS_OUTPUT_FORMAT", "")

        # Note: This will fail validation since "" is not a valid Literal value
        # This tests that empty string IS being read (not ignored)
        with pytest.raises(Exception):  # ValidationError for invalid Literal
            GlobalSettings()

    def test_env_unset_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset ENV uses model default."""
        monkeypatch.delenv("BUVIS_OUTPUT_FORMAT", raising=False)
        monkeypatch.delenv("BUVIS_DEBUG", raising=False)
        monkeypatch.delenv("BUVIS_LOG_LEVEL", raising=False)

        settings = GlobalSettings()

        assert settings.output_format == "text"
        assert settings.debug is False
        assert settings.log_level == "INFO"


class TestYamlAbsentKey:
    """YAML absent key falls back to default."""

    def test_yaml_missing_key_uses_default(self, tmp_path: Path) -> None:
        """YAML with missing key uses model default."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: true\n")  # no log_level or output_format

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings, config_path=config)

        assert settings.debug is True
        assert settings.log_level == "INFO"  # default
        assert settings.output_format == "text"  # default

    def test_empty_yaml_uses_all_defaults(self, tmp_path: Path) -> None:
        """Empty YAML file uses all defaults."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings, config_path=config)

        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.output_format == "text"


class TestCliNoneFallthrough:
    """CLI None values fall through to lower priority sources."""

    def test_cli_none_falls_through_to_yaml(self, tmp_path: Path) -> None:
        """CLI=None falls through to YAML value."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: true\n")

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings, config_path=config, cli_overrides={"debug": None})

        assert settings.debug is True  # YAML wins

    def test_cli_none_falls_through_to_default(self) -> None:
        """CLI=None falls through to default."""
        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings, cli_overrides={"debug": None})

        assert settings.debug is False  # default


class TestInvalidValueFromAnySources:
    """Invalid values from any source raise ValidationError."""

    def test_invalid_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid value from ENV raises ValidationError."""
        from pydantic import ValidationError

        monkeypatch.setenv("BUVIS_LOG_LEVEL", "INVALID")

        with pytest.raises(ValidationError):
            GlobalSettings()

    def test_invalid_from_cli(self) -> None:
        """Invalid value from CLI raises ValidationError."""
        from buvis.pybase.configuration import ConfigurationError

        resolver = ConfigResolver()

        with pytest.raises(ConfigurationError):
            resolver.resolve(GlobalSettings, cli_overrides={"log_level": "INVALID"})


class TestPrecedenceEdgeCases:
    """Edge cases in precedence chain."""

    def test_partial_cli_overrides(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI only overrides specified fields."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: true\nlog_level: WARNING\n")
        monkeypatch.setenv("BUVIS_OUTPUT_FORMAT", "json")

        resolver = ConfigResolver()
        settings = resolver.resolve(
            GlobalSettings,
            config_path=config,
            cli_overrides={"debug": False},  # Only override debug
        )

        assert settings.debug is False  # CLI
        assert settings.log_level == "WARNING"  # YAML (no CLI override)
        assert settings.output_format == "json"  # ENV

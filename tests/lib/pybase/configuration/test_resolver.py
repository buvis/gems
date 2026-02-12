from __future__ import annotations

import os
from pathlib import Path

import pytest
from buvis.pybase.configuration import ConfigurationError
from buvis.pybase.configuration.resolver import (
    ConfigResolver,
    _extract_tool_name,
    _load_yaml_config,
)
from buvis.pybase.configuration.settings import GlobalSettings


class TestExtractToolName:
    def test_global_settings_prefix_returns_none(self) -> None:
        assert _extract_tool_name("BUVIS_") is None

    def test_photo_prefix_returns_photo(self) -> None:
        assert _extract_tool_name("BUVIS_PHOTO_") == "photo"

    def test_hcm_tools_prefix_returns_hcm_tools(self) -> None:
        assert _extract_tool_name("BUVIS_HCM_TOOLS_") == "hcm_tools"

    def test_empty_string_returns_none(self) -> None:
        assert _extract_tool_name("") is None

    def test_invalid_pattern_returns_none(self) -> None:
        assert _extract_tool_name("INVALID_PREFIX_") is None


class TestConfigResolverResolve:
    def test_resolve_applies_cli_overrides(self) -> None:
        """CLI overrides are applied to settings."""
        overrides = {"debug": True, "log_level": "DEBUG"}
        resolver = ConfigResolver()

        settings = resolver.resolve(GlobalSettings, cli_overrides=overrides)

        assert settings.debug is True
        assert settings.log_level == "DEBUG"

    def test_resolve_sets_config_dir_env(self, monkeypatch) -> None:
        """config_dir is set during resolve but restored afterward."""
        monkeypatch.delenv("BUVIS_CONFIG_DIR", raising=False)

        resolver = ConfigResolver()
        config_dir = "/tmp/buvis"
        resolver.resolve(GlobalSettings, config_dir=config_dir)

        # Env var should be removed after resolve (wasn't set before)
        assert "BUVIS_CONFIG_DIR" not in os.environ

    def test_resolve_restores_original_config_dir(self, monkeypatch) -> None:
        """config_dir restores original env var value after resolve."""
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "/original/path")

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings, config_dir="/tmp/override")

        assert os.environ["BUVIS_CONFIG_DIR"] == "/original/path"

    def test_resolve_without_config_dir_leaves_env_unchanged(self, monkeypatch) -> None:
        """resolve() without config_dir doesn't modify env var."""
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "/existing")

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings)

        assert os.environ["BUVIS_CONFIG_DIR"] == "/existing"


class TestConfigResolverPrecedence:
    """Tests for CLI > ENV > YAML > Defaults precedence."""

    def test_cli_wins_when_all_sources_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI overrides take precedence over ENV and YAML."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: false\nlog_level: WARNING\n")
        monkeypatch.setenv("BUVIS_DEBUG", "false")
        monkeypatch.setenv("BUVIS_LOG_LEVEL", "ERROR")

        resolver = ConfigResolver()
        settings = resolver.resolve(
            GlobalSettings,
            config_path=config,
            cli_overrides={"debug": True, "log_level": "DEBUG"},
        )

        assert settings.debug is True
        assert settings.log_level == "DEBUG"

    def test_env_wins_when_no_cli(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """ENV overrides YAML when no CLI provided."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: false\nlog_level: WARNING\n")
        monkeypatch.setenv("BUVIS_DEBUG", "true")
        monkeypatch.setenv("BUVIS_LOG_LEVEL", "ERROR")

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings, config_path=config)

        assert settings.debug is True
        assert settings.log_level == "ERROR"

    def test_yaml_wins_when_no_cli_or_env(self, tmp_path: Path) -> None:
        """YAML overrides defaults when no CLI or ENV."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: true\nlog_level: WARNING\n")

        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings, config_path=config)

        assert settings.debug is True
        assert settings.log_level == "WARNING"

    def test_default_used_when_only_default(self) -> None:
        """Defaults used when no other sources set values."""
        resolver = ConfigResolver()

        settings = resolver.resolve(GlobalSettings)

        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_cli_none_falls_through(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI=None falls through to ENV value."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: false\n")
        monkeypatch.setenv("BUVIS_DEBUG", "true")

        resolver = ConfigResolver()
        settings = resolver.resolve(
            GlobalSettings,
            config_path=config,
            cli_overrides={"debug": None},
        )

        # None in CLI means "not provided", so ENV wins
        assert settings.debug is True


class TestLoadYamlConfig:
    """Tests for _load_yaml_config function."""

    def test_valid_yaml_returns_dict(self, tmp_path: Path) -> None:
        """Valid YAML file returns parsed dict."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: true\nlog_level: DEBUG\n")

        result = _load_yaml_config(config)

        assert result == {"debug": True, "log_level": "DEBUG"}

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Missing file returns empty dict."""
        missing = tmp_path / "nonexistent.yaml"

        result = _load_yaml_config(missing)

        assert result == {}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Empty file returns empty dict."""
        empty = tmp_path / "empty.yaml"
        empty.write_text("")

        result = _load_yaml_config(empty)

        assert result == {}

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """Invalid YAML raises ConfigurationError with file path."""
        invalid = tmp_path / "invalid.yaml"
        invalid.write_text("key: [broken")

        with pytest.raises(ConfigurationError) as exc_info:
            _load_yaml_config(invalid)

        assert str(invalid) in str(exc_info.value)

    def test_invalid_yaml_includes_line_number(self, tmp_path: Path) -> None:
        """ConfigurationError includes line number from problem_mark."""
        invalid = tmp_path / "bad.yaml"
        # Error on line 2 (0-indexed line 1, so +1 = 2)
        invalid.write_text("valid: true\nbroken: [unclosed")

        with pytest.raises(ConfigurationError) as exc_info:
            _load_yaml_config(invalid)

        assert ":2:" in str(exc_info.value) or ":3:" in str(exc_info.value)

    def test_permission_denied_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """PermissionError returns empty dict."""
        config = tmp_path / "locked.yaml"
        config.write_text("key: value")

        original_open = Path.open

        def raise_permission(self, *args, **kwargs):
            if self == config:
                raise PermissionError("Access denied")
            return original_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", raise_permission)

        result = _load_yaml_config(config)

        assert result == {}

    def test_env_var_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """BUVIS_CONFIG_FILE env var takes precedence."""
        config = tmp_path / "custom.yaml"
        config.write_text("custom: true\n")
        monkeypatch.setenv("BUVIS_CONFIG_FILE", str(config))

        result = _load_yaml_config()

        assert result == {"custom": True}

    def test_explicit_path_param(self, tmp_path: Path) -> None:
        """Explicit file_path param is used."""
        config = tmp_path / "explicit.yaml"
        config.write_text("explicit: yes\n")

        result = _load_yaml_config(config)

        assert result == {"explicit": True}


class TestValidationErrorHandling:
    """Tests for validation error handling in ConfigResolver."""

    def test_invalid_log_level_raises_config_error(self, tmp_path: Path) -> None:
        """Invalid log_level raises ConfigurationError with field path."""
        config = tmp_path / "config.yaml"
        config.write_text("log_level: INVALID\n")

        resolver = ConfigResolver()

        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve(GlobalSettings, config_path=config)

        assert "log_level" in str(exc_info.value)

    def test_invalid_debug_type_raises_config_error(self, tmp_path: Path) -> None:
        """Invalid debug type raises ConfigurationError."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: not_a_bool\n")

        resolver = ConfigResolver()

        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve(GlobalSettings, config_path=config)

        assert "debug" in str(exc_info.value)

    def test_error_message_is_user_friendly(self, tmp_path: Path) -> None:
        """Error message contains 'Configuration validation failed'."""
        config = tmp_path / "config.yaml"
        config.write_text("log_level: INVALID\n")

        resolver = ConfigResolver()

        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve(GlobalSettings, config_path=config)

        assert "Configuration validation failed" in str(exc_info.value)


class TestSecretMaskingInErrors:
    """Tests for secret masking in validation error messages."""

    def test_sensitive_field_error_masked(self) -> None:
        """Error on sensitive field shows 'invalid value (hidden)'."""
        from buvis.pybase.configuration.resolver import _format_validation_errors
        from pydantic import ValidationError
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class TestSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_")
            api_key: int  # Will fail with string

        try:
            TestSettings(api_key="not_an_int")
        except ValidationError as e:
            result = _format_validation_errors(e)

        assert "api_key: invalid value (hidden)" in result
        assert "not_an_int" not in result

    def test_nested_sensitive_field_masked(self) -> None:
        """Error on nested sensitive field is masked."""
        from buvis.pybase.configuration.resolver import _format_validation_errors
        from pydantic import BaseModel, ValidationError
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class DbConfig(BaseModel):
            password: int  # Will fail with string

        class TestSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_")
            database: DbConfig

        try:
            TestSettings(database={"password": "secret_value"})
        except ValidationError as e:
            result = _format_validation_errors(e)

        assert "invalid value (hidden)" in result
        assert "secret_value" not in result

    def test_non_sensitive_field_shows_message(self) -> None:
        """Error on non-sensitive field shows actual error message."""
        from buvis.pybase.configuration.resolver import _format_validation_errors
        from pydantic import ValidationError
        from pydantic_settings import BaseSettings, SettingsConfigDict

        class TestSettings(BaseSettings):
            model_config = SettingsConfigDict(env_prefix="TEST_")
            count: int

        try:
            TestSettings(count="not_a_number")
        except ValidationError as e:
            result = _format_validation_errors(e)

        assert "count:" in result
        assert "invalid value (hidden)" not in result


class TestSecurityConstraints:
    """Tests for security constraints in ConfigResolver."""

    def test_settings_immutable_after_resolve(self) -> None:
        """Settings are frozen and cannot be modified."""
        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings)

        with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen
            settings.debug = True

    def test_fail_fast_validates_at_resolve(self, tmp_path: Path) -> None:
        """Validation happens at resolve(), not at field access."""
        config = tmp_path / "config.yaml"
        config.write_text("log_level: INVALID\n")

        resolver = ConfigResolver()

        # Error raised at resolve(), not when accessing log_level
        with pytest.raises(ConfigurationError):
            resolver.resolve(GlobalSettings, config_path=config)


class TestConfigSource:
    """Tests for ConfigSource enum."""

    def test_enum_values(self) -> None:
        """ConfigSource has correct string values."""
        from buvis.pybase.configuration import ConfigSource

        assert ConfigSource.DEFAULT.value == "default"
        assert ConfigSource.YAML.value == "yaml"
        assert ConfigSource.ENV.value == "env"
        assert ConfigSource.CLI.value == "cli"

    def test_enum_membership(self) -> None:
        """ConfigSource has exactly 4 members."""
        from buvis.pybase.configuration import ConfigSource

        assert len(ConfigSource) == 4


class TestConfigResolverSourceTracking:
    """Tests for source tracking in ConfigResolver."""

    def test_sources_populated_after_resolve(self) -> None:
        """sources dict populated for each field after resolve()."""
        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings)

        assert "debug" in resolver.sources
        assert "log_level" in resolver.sources

    def test_cli_source_tracked(self) -> None:
        """CLI overrides tracked as ConfigSource.CLI."""
        from buvis.pybase.configuration import ConfigSource

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings, cli_overrides={"debug": True})

        assert resolver.sources["debug"] == ConfigSource.CLI

    def test_env_source_tracked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ENV values tracked as ConfigSource.ENV."""
        from buvis.pybase.configuration import ConfigSource

        monkeypatch.setenv("BUVIS_DEBUG", "true")

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings)

        assert resolver.sources["debug"] == ConfigSource.ENV

    def test_yaml_source_tracked(self, tmp_path: Path) -> None:
        """YAML values tracked as ConfigSource.YAML."""
        from buvis.pybase.configuration import ConfigSource

        config = tmp_path / "config.yaml"
        config.write_text("debug: true\n")

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings, config_path=config)

        assert resolver.sources["debug"] == ConfigSource.YAML

    def test_default_source_tracked(self) -> None:
        """Default values tracked as ConfigSource.DEFAULT."""
        from buvis.pybase.configuration import ConfigSource

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings)

        assert resolver.sources["debug"] == ConfigSource.DEFAULT
        assert resolver.sources["log_level"] == ConfigSource.DEFAULT

    def test_mixed_sources(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Different fields can have different sources."""
        from buvis.pybase.configuration import ConfigSource

        config = tmp_path / "config.yaml"
        config.write_text("log_level: WARNING\n")
        monkeypatch.setenv("BUVIS_DEBUG", "true")

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings, config_path=config)

        # debug from ENV, log_level from YAML
        assert resolver.sources["debug"] == ConfigSource.ENV
        assert resolver.sources["log_level"] == ConfigSource.YAML


class TestConfigResolverLogging:
    """Tests for DEBUG logging in ConfigResolver."""

    def test_log_sources_called(self, caplog: pytest.LogCaptureFixture) -> None:
        """DEBUG log entries created for each field."""
        import logging

        resolver = ConfigResolver()

        with caplog.at_level(logging.DEBUG):
            resolver.resolve(GlobalSettings)

        # Check field names logged
        assert "debug" in caplog.text
        assert "log_level" in caplog.text

    def test_source_tracking_logs_no_values(self, caplog: pytest.LogCaptureFixture) -> None:
        """Source tracking log messages contain field names but no values."""
        import logging

        resolver = ConfigResolver()

        with caplog.at_level(logging.DEBUG):
            resolver.resolve(GlobalSettings, cli_overrides={"debug": True})

        # Source tracking logs field name and source, not value
        source_logs = [r for r in caplog.records if "from cli" in r.message]
        assert len(source_logs) == 1
        assert "debug" in source_logs[0].message
        assert "True" not in source_logs[0].message


class TestConfigResolverSourcesProperty:
    """Tests for sources property."""

    def test_sources_returns_copy(self) -> None:
        """sources property returns defensive copy."""
        from buvis.pybase.configuration import ConfigSource

        resolver = ConfigResolver()
        resolver.resolve(GlobalSettings)

        sources_copy = resolver.sources
        sources_copy["debug"] = ConfigSource.CLI  # Modify copy

        # Original unchanged
        assert resolver.sources["debug"] == ConfigSource.DEFAULT

    def test_sources_empty_before_resolve(self) -> None:
        """sources is empty before resolve() called."""
        resolver = ConfigResolver()

        assert resolver.sources == {}

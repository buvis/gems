"""Tests for Click integration with BUVIS configuration."""

from __future__ import annotations

from pathlib import Path

import click
import pytest
from buvis.pybase.configuration import buvis_options, get_settings
from buvis.pybase.configuration.settings import GlobalSettings
from click.testing import CliRunner
from pydantic import BaseModel


@pytest.fixture
def runner() -> CliRunner:
    """Create Click test runner."""
    return CliRunner()


@pytest.fixture
def custom_settings_cls() -> type[GlobalSettings]:
    class CustomSettings(GlobalSettings):
        custom_field: str = "default"

    return CustomSettings


class TestBuvisOptionsHelp:
    """Tests for --help output."""

    def test_debug_option_in_help(self, runner: CliRunner) -> None:
        """--debug/--no-debug appears in help."""

        @click.command()
        @buvis_options
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--help"])

        assert "--debug" in result.output
        assert "--no-debug" in result.output

    def test_log_level_option_in_help(self, runner: CliRunner) -> None:
        """--log-level appears in help with choices."""

        @click.command()
        @buvis_options
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--help"])

        assert "--log-level" in result.output
        assert "debug" in result.output.lower()

    def test_config_dir_option_in_help(self, runner: CliRunner) -> None:
        """--config-dir appears in help."""

        @click.command()
        @buvis_options
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--help"])

        assert "--config-dir" in result.output

    def test_config_option_in_help(self, runner: CliRunner) -> None:
        """--config appears in help."""

        @click.command()
        @buvis_options
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--help"])

        assert "--config" in result.output


class TestBuvisOptionsContextInjection:
    """Tests for settings injection into context."""

    def test_settings_injected_into_context(self, runner: CliRunner) -> None:
        """Settings object exists in ctx.obj['settings']."""
        captured_settings = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured_settings.append(ctx.obj.get("settings"))

        runner.invoke(cmd, [])

        assert len(captured_settings) == 1
        assert isinstance(captured_settings[0], GlobalSettings)

    def test_default_settings_values(self, runner: CliRunner) -> None:
        """Default settings have expected values."""
        captured_settings = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured_settings.append(ctx.obj["settings"])

        runner.invoke(cmd, [])

        settings = captured_settings[0]
        assert settings.debug is False
        assert settings.log_level == "INFO"


class TestBuvisOptionsCLIOverrides:
    """Tests for CLI option overrides."""

    def test_debug_flag_overrides_default(self, runner: CliRunner) -> None:
        """--debug sets debug=True."""
        captured_settings = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured_settings.append(ctx.obj["settings"])

        runner.invoke(cmd, ["--debug"])

        assert captured_settings[0].debug is True

    def test_no_debug_flag(self, runner: CliRunner) -> None:
        """--no-debug sets debug=False."""
        captured_settings = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured_settings.append(ctx.obj["settings"])

        runner.invoke(cmd, ["--no-debug"])

        assert captured_settings[0].debug is False

    def test_log_level_override(self, runner: CliRunner) -> None:
        """--log-level sets log_level."""
        captured_settings = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured_settings.append(ctx.obj["settings"])

        runner.invoke(cmd, ["--log-level", "DEBUG"])

        assert captured_settings[0].log_level == "DEBUG"


class TestBuvisOptionsParameterized:
    """Tests for decorator invocation styles and custom settings."""

    def test_bare_decorator_works(self, runner: CliRunner) -> None:
        """@buvis_options without parentheses uses GlobalSettings."""
        captured = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured.append((ctx.obj["settings"], ctx.obj[GlobalSettings]))

        runner.invoke(cmd, [])

        settings, cached = captured[0]
        assert isinstance(settings, GlobalSettings)
        assert settings is cached

    def test_empty_parens_works(self, runner: CliRunner) -> None:
        """@buvis_options() without args still uses GlobalSettings."""
        captured = []

        @click.command()
        @buvis_options()
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured.append((ctx.obj["settings"], get_settings(ctx)))

        runner.invoke(cmd, [])

        settings, resolved = captured[0]
        assert isinstance(settings, GlobalSettings)
        assert settings is resolved

    def test_custom_settings_class(self, runner: CliRunner, custom_settings_cls: type[GlobalSettings]) -> None:
        """Custom settings class is used and includes custom_field."""
        captured = []

        @click.command()
        @buvis_options(settings_class=custom_settings_cls)
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured.append(ctx.obj[custom_settings_cls])

        runner.invoke(cmd, [])

        settings = captured[0]
        assert isinstance(settings, custom_settings_cls)
        assert settings.custom_field == "default"

    def test_settings_cached_by_class(self, runner: CliRunner, custom_settings_cls: type[GlobalSettings]) -> None:
        """Settings instance is stored by class key in ctx.obj."""
        captured = []

        @click.command()
        @buvis_options(settings_class=custom_settings_cls)
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured.append(ctx.obj[custom_settings_cls])

        runner.invoke(cmd, [])

        assert len(captured) == 1
        assert isinstance(captured[0], custom_settings_cls)

    def test_global_settings_backward_compat(self, runner: CliRunner) -> None:
        """Legacy ctx.obj['settings'] remains for GlobalSettings."""
        captured = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured.append((ctx.obj[GlobalSettings], ctx.obj["settings"]))

        runner.invoke(cmd, [])

        by_class, legacy = captured[0]
        assert isinstance(legacy, GlobalSettings)
        assert legacy is by_class

    def test_non_global_settings_no_legacy_key(
        self, runner: CliRunner, custom_settings_cls: type[GlobalSettings]
    ) -> None:
        """When using custom settings, ctx.obj['settings'] is not set."""
        captured = []

        @click.command()
        @buvis_options(settings_class=custom_settings_cls)
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured.append(ctx.obj[custom_settings_cls])
            captured.append("settings" in ctx.obj)

        runner.invoke(cmd, [])

        settings, legacy_present = captured
        assert isinstance(settings, custom_settings_cls)
        assert legacy_present is False


class TestBuvisOptionsConfigFile:
    """Tests for config file loading."""

    def test_config_file_loaded(self, runner: CliRunner, tmp_path: Path) -> None:
        """--config loads YAML file."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: true\n")
        captured_settings = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured_settings.append(ctx.obj["settings"])

        runner.invoke(cmd, ["--config", str(config)])

        assert captured_settings[0].debug is True

    def test_cli_overrides_config_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """CLI options override config file values."""
        config = tmp_path / "config.yaml"
        config.write_text("debug: true\nlog_level: ERROR\n")
        captured_settings = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured_settings.append(ctx.obj["settings"])

        runner.invoke(cmd, ["--config", str(config), "--no-debug"])

        assert captured_settings[0].debug is False
        assert captured_settings[0].log_level == "ERROR"


class TestGetSettings:
    """Tests for get_settings helper function."""

    def test_returns_settings_from_context(self, runner: CliRunner) -> None:
        """get_settings returns settings from ctx.obj."""
        captured = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            settings = get_settings(ctx)
            captured.append(settings)

        runner.invoke(cmd, [])

        assert len(captured) == 1
        assert isinstance(captured[0], GlobalSettings)

    def test_returns_same_object_as_context(self, runner: CliRunner) -> None:
        """get_settings returns identical object to ctx.obj['settings']."""
        captured = []

        @click.command()
        @buvis_options
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            captured.append((ctx.obj["settings"], get_settings(ctx)))

        runner.invoke(cmd, [])

        assert captured[0][0] is captured[0][1]

    def test_raises_when_ctx_obj_none(self) -> None:
        """RuntimeError raised when ctx.obj is None."""
        from unittest.mock import MagicMock

        ctx = MagicMock(spec=click.Context)
        ctx.obj = None

        with pytest.raises(RuntimeError, match="buvis_options decorator not applied"):
            get_settings(ctx)

    def test_raises_when_settings_key_missing(self) -> None:
        """RuntimeError raised when 'settings' key missing."""
        from unittest.mock import MagicMock

        ctx = MagicMock(spec=click.Context)
        ctx.obj = {}

        with pytest.raises(RuntimeError, match="buvis_options decorator not applied"):
            get_settings(ctx)

    def test_raises_when_ctx_obj_has_other_keys(self) -> None:
        """RuntimeError raised when ctx.obj has other keys but not 'settings'."""
        from unittest.mock import MagicMock

        ctx = MagicMock(spec=click.Context)
        ctx.obj = {"other": "value"}

        with pytest.raises(RuntimeError, match="buvis_options decorator not applied"):
            get_settings(ctx)

    def test_returns_custom_settings_class(self, custom_settings_cls: type[GlobalSettings]) -> None:
        """get_settings returns requested custom settings instance."""
        from unittest.mock import MagicMock

        ctx = MagicMock(spec=click.Context)
        settings = custom_settings_cls()
        ctx.obj = {custom_settings_cls: settings}

        resolved = get_settings(ctx, custom_settings_cls)

        assert resolved is settings

    def test_raises_when_settings_class_not_in_context(self, custom_settings_cls: type[GlobalSettings]) -> None:
        """RuntimeError raised when requested class is missing in ctx.obj."""
        from unittest.mock import MagicMock

        ctx = MagicMock(spec=click.Context)
        ctx.obj = {GlobalSettings: GlobalSettings()}

        with pytest.raises(RuntimeError, match=custom_settings_cls.__name__):
            get_settings(ctx, custom_settings_cls)

    def test_error_message_includes_class_name(self, custom_settings_cls: type[GlobalSettings]) -> None:
        """Error message includes class name and decorator hint."""
        from unittest.mock import MagicMock

        ctx = MagicMock(spec=click.Context)
        ctx.obj = {}

        with pytest.raises(RuntimeError) as excinfo:
            get_settings(ctx, custom_settings_cls)

        message = str(excinfo.value)
        assert custom_settings_cls.__name__ in message
        assert f"@buvis_options(settings_class={custom_settings_cls.__name__})" in message


class TestClickIntegration:
    """Integration tests for Click group/subcommand settings inheritance."""

    def test_settings_inherited_in_subcommand(self, runner: CliRunner) -> None:
        """Settings from parent @buvis_options are accessible in subcommands."""

        @click.group()
        @buvis_options
        @click.pass_context
        def cli(ctx: click.Context) -> None:
            pass

        @cli.command()
        @click.pass_context
        def process(ctx: click.Context) -> None:
            s = get_settings(ctx)
            click.echo(f"debug={s.debug}")

        result = runner.invoke(cli, ["--debug", "process"])

        assert "debug=True" in result.output
        assert result.exit_code == 0

    def test_get_settings_returns_same_object_in_group_and_subcommand(self, runner: CliRunner) -> None:
        """get_settings returns identical object in group and subcommand (PRD #6)."""
        results: list[int] = []

        @click.group()
        @buvis_options
        @click.pass_context
        def cli(ctx: click.Context) -> None:
            results.append(id(get_settings(ctx)))

        @cli.command()
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            results.append(id(get_settings(ctx)))

        runner.invoke(cli, ["cmd"])

        assert len(results) == 2
        assert results[0] == results[1]  # Same object

    def test_settings_accessible_in_multiple_levels(self, runner: CliRunner) -> None:
        """Settings accessible at group and command level."""
        captured: list[str] = []

        @click.group()
        @buvis_options
        @click.pass_context
        def cli(ctx: click.Context) -> None:
            s = get_settings(ctx)
            captured.append(f"group={s.log_level}")

        @cli.command()
        @click.pass_context
        def cmd(ctx: click.Context) -> None:
            s = get_settings(ctx)
            captured.append(f"cmd={s.log_level}")

        runner.invoke(cli, ["--log-level", "DEBUG", "cmd"])

        assert "group=DEBUG" in captured
        assert "cmd=DEBUG" in captured

    def test_multiple_subcommands_share_settings(self, runner: CliRunner) -> None:
        """Multiple subcommands in same invocation share settings object."""
        captured_ids: list[int] = []

        @click.group(chain=True)
        @buvis_options
        @click.pass_context
        def cli(ctx: click.Context) -> None:
            pass

        @cli.command()
        @click.pass_context
        def cmd1(ctx: click.Context) -> None:
            captured_ids.append(id(get_settings(ctx)))

        @cli.command()
        @click.pass_context
        def cmd2(ctx: click.Context) -> None:
            captured_ids.append(id(get_settings(ctx)))

        runner.invoke(cli, ["cmd1", "cmd2"])

        assert len(captured_ids) == 2
        assert captured_ids[0] == captured_ids[1]


class TestConfigCreate:
    """Tests for --config-create option."""

    def test_config_create_in_help(self, runner: CliRunner) -> None:
        @click.command()
        @buvis_options
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--help"])
        assert "--config-create" in result.output
        assert "Generate YAML config template" in result.output

    def test_config_create_writes_file(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "config.yaml"

        @click.command()
        @buvis_options
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--config-create", str(output)])
        assert result.exit_code == 0
        assert output.exists()
        assert "Config written to" in result.output

    def test_config_create_command_not_executed(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "config.yaml"
        executed = []

        @click.command()
        @buvis_options
        def cmd() -> None:
            executed.append(True)

        result = runner.invoke(cmd, ["--config-create", str(output)])
        assert result.exit_code == 0
        assert len(executed) == 0  # Command body never runs

    def test_config_create_existing_file_error(self, runner: CliRunner, tmp_path: Path) -> None:
        existing = tmp_path / "config.yaml"
        existing.write_text("old")

        @click.command()
        @buvis_options
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--config-create", str(existing)])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_config_create_uses_command_name(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "config.yaml"

        @click.command(name="mycommand")
        @buvis_options
        def cmd() -> None:
            pass

        runner.invoke(cmd, ["--config-create", str(output)])
        content = output.read_text()
        assert "Configuration for mycommand" in content

    def test_config_create_with_custom_settings_class(self, runner: CliRunner, tmp_path: Path) -> None:
        class CustomAppSettings(BaseModel):
            custom_value: str = "test"
            api_key: str | None = None

        output = tmp_path / "config.yaml"

        @click.command()
        @buvis_options(settings_class=CustomAppSettings)
        def cmd() -> None:
            pass

        result = runner.invoke(cmd, ["--config-create", str(output)])
        assert result.exit_code == 0
        assert output.exists()
        assert "custom_value:" in output.read_text()

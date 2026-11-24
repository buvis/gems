"""Tests for the passive auto-update check's settings and option resolution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import click
import pytest
from buvis.pybase.configuration import buvis_options
from buvis.pybase.configuration.settings import GlobalSettings
from click.testing import CliRunner, Result
from pydantic_settings import SettingsConfigDict

if TYPE_CHECKING:
    from pathlib import Path


class FooSettings(GlobalSettings):
    """Tool settings with their own ``BUVIS_FOO_`` env prefix."""

    model_config = SettingsConfigDict(
        env_prefix="BUVIS_FOO_",
        env_nested_delimiter="__",
        case_sensitive=False,
        frozen=True,
        extra="forbid",
    )


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME, XDG and cwd at tmp_path and drop every BUVIS_* variable.

    Returns:
        The isolated working directory (also the process cwd).
    """
    for key in [k for k in os.environ if k.startswith("BUVIS_")]:
        monkeypatch.delenv(key)
    home = tmp_path / "home"
    (home / ".config" / "buvis").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def _invoke(args: list[str], settings_class: type[GlobalSettings] | None = None) -> tuple[Result, MagicMock]:
    """Run a throwaway buvis command and return its result and the update mock."""
    decorator = buvis_options if settings_class is None else buvis_options(settings_class=settings_class)

    @click.command()
    @decorator
    @click.argument("rest", nargs=-1)
    def cmd(rest: tuple[str, ...]) -> None:
        pass

    with patch("buvis.pybase.updater.check_and_update") as mock_update:
        result = CliRunner().invoke(cmd, args)
    return result, mock_update


def _config(directory: Path, auto_update: bool, name: str = "config.yaml") -> Path:
    """Write a YAML config with the given auto_update value and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f"auto_update: {str(auto_update).lower()}\n")
    return path


class TestEnvPrecedence:
    """The global env fallback never outranks a more specific knob."""

    def test_env_true_beats_yaml_false_for_a_prefixless_settings_class(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A set env var beats YAML even when its value equals the field default.

        For a class with no tool prefix, BUVIS_AUTO_UPDATE *is* the tool
        variable, so the resolved value decides, and the environment outranks
        the config file.
        """
        monkeypatch.setenv("BUVIS_AUTO_UPDATE", "true")
        config = _config(tmp_path / "c", auto_update=False)

        result, mock_update = _invoke(["--config", str(config)])

        assert result.exit_code == 0
        mock_update.assert_called_once()
        assert mock_update.call_args.args[0].auto_update is True

    def test_tool_env_true_beats_yaml_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """BUVIS_<TOOL>_AUTO_UPDATE=true switches the check back on over YAML false."""
        monkeypatch.setenv("BUVIS_FOO_AUTO_UPDATE", "true")
        config = _config(tmp_path / "c", auto_update=False)

        result, mock_update = _invoke(["--config", str(config)], FooSettings)

        assert result.exit_code == 0
        mock_update.assert_called_once()
        assert mock_update.call_args.args[0].auto_update is True

    def test_global_env_true_runs_tool_check_despite_yaml_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same rule for a tool class: no BUVIS_FOO_AUTO_UPDATE, so the global env applies.

        The updater re-tests ``settings.auto_update``, so the settings it is
        handed must carry the decision, not the YAML value.
        """
        monkeypatch.setenv("BUVIS_AUTO_UPDATE", "true")
        config = _config(tmp_path / "c", auto_update=False)

        result, mock_update = _invoke(["--config", str(config)], FooSettings)

        assert result.exit_code == 0
        mock_update.assert_called_once()
        assert mock_update.call_args.args[0].auto_update is True

    def test_tool_env_false_beats_global_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """BUVIS_<TOOL>_AUTO_UPDATE wins over BUVIS_AUTO_UPDATE."""
        monkeypatch.setenv("BUVIS_AUTO_UPDATE", "true")
        monkeypatch.setenv("BUVIS_FOO_AUTO_UPDATE", "false")

        result, mock_update = _invoke([], FooSettings)

        assert result.exit_code == 0
        mock_update.assert_not_called()

    def test_lowercase_tool_env_false_still_beats_global_env_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The tool variable is read case-insensitively, as the settings read it."""
        monkeypatch.setenv("BUVIS_AUTO_UPDATE", "true")
        monkeypatch.setenv("buvis_foo_auto_update", "false")

        result, mock_update = _invoke([], FooSettings)

        assert result.exit_code == 0
        mock_update.assert_not_called()

    @pytest.mark.parametrize("name", ["buvis_auto_update", "Buvis_Auto_Update"])
    def test_global_auto_update_variable_is_read_in_any_letter_case(
        self, name: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The global switch is read case-insensitively, like every other setting."""
        from buvis.pybase.configuration.click_integration import _update_enabled

        monkeypatch.setenv(name, "false")

        assert _update_enabled(FooSettings, FooSettings()) is False

    def test_malformed_global_env_skips_check_without_raising(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A bad BUVIS_AUTO_UPDATE degrades the check, --help still works."""
        monkeypatch.setenv("BUVIS_AUTO_UPDATE", "maybe")

        result, mock_update = _invoke(["--help"])

        assert result.exit_code == 0
        mock_update.assert_not_called()


class TestOptionExtraction:
    """--config / --config-dir are read from raw argv exactly like Click would."""

    @pytest.mark.parametrize(("value", "called"), [(False, False), (True, True)])
    def test_config_dir_value_decides_check(self, tmp_path: Path, value: bool, called: bool) -> None:
        """auto_update in the --config-dir config decides whether the check runs."""
        directory = tmp_path / "d"
        _config(directory, value)

        result, mock_update = _invoke(["--config-dir", str(directory)])

        assert result.exit_code == 0
        assert mock_update.called is called

    @pytest.mark.parametrize(("file_value", "dir_value"), [(False, True), (True, False)])
    def test_config_file_beats_config_dir(self, tmp_path: Path, file_value: bool, dir_value: bool) -> None:
        """--config wins over --config-dir absolutely."""
        config = _config(tmp_path / "f", file_value)
        directory = tmp_path / "d"
        _config(directory, dir_value)

        result, mock_update = _invoke(["--config", str(config), "--config-dir", str(directory)])

        assert result.exit_code == 0
        assert mock_update.called is file_value

    @pytest.mark.parametrize(("first", "last"), [(False, True), (True, False)])
    def test_repeated_config_last_value_wins(self, tmp_path: Path, first: bool, last: bool) -> None:
        """With --config A --config B, B decides, matching Click."""
        a = _config(tmp_path / "a", first)
        b = _config(tmp_path / "b", last)

        result, mock_update = _invoke(["--config", str(a), "--config", str(b)])

        assert result.exit_code == 0
        assert mock_update.called is last

    def test_trailing_valueless_config_keeps_earlier_value(self, tmp_path: Path) -> None:
        """A bare trailing --config does not clear the last valued occurrence.

        The update check runs inside the ``parse_args`` patch, before Click
        validates the options, so it sees the earlier value even though Click
        then rejects the valueless trailing flag with exit code 2.
        """
        config = _config(tmp_path / "a", auto_update=False)

        result, mock_update = _invoke(["--config", str(config), "--config"])

        mock_update.assert_not_called()
        assert result.exit_code == 2

    def test_empty_config_dir_value_is_absent_not_cwd(
        self, isolated_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--config-dir= must not turn the cwd into the top-priority config dir.

        Path("") is the cwd. If an empty value were passed on as a directory it
        would outrank BUVIS_CONFIG_DIR and the cwd file (auto_update: false)
        would suppress the check instead of the env dir (auto_update: true).
        """
        env_dir = tmp_path / "envdir"
        _config(env_dir, auto_update=True)
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(env_dir))
        _config(isolated_env, auto_update=False)

        _, mock_update = _invoke(["--config-dir="])

        mock_update.assert_called_once()

    @pytest.mark.parametrize(("value", "called"), [(False, False), (True, True)])
    def test_config_equals_form_is_honoured(self, tmp_path: Path, value: bool, called: bool) -> None:
        """--config=VALUE is read the same as --config VALUE."""
        config = _config(tmp_path / "c", value)

        result, mock_update = _invoke([f"--config={config}"])

        assert result.exit_code == 0
        assert mock_update.called is called

    def test_option_after_end_of_options_sentinel_is_ignored(self, tmp_path: Path) -> None:
        """A literal --config-dir after -- is a positional argument."""
        directory = tmp_path / "d"
        _config(directory, auto_update=False)

        result, mock_update = _invoke(["--", "--config-dir", str(directory)])

        assert result.exit_code == 0
        mock_update.assert_called_once()


class TestDefaultDiscovery:
    """Without --config/--config-dir, discovered config files decide."""

    @pytest.mark.parametrize(
        ("settings_class", "filename"),
        [(None, "config.yaml"), (FooSettings, "buvis-foo.yaml")],
    )
    def test_discovered_yaml_false_suppresses_check(
        self, tmp_path: Path, settings_class: type[GlobalSettings] | None, filename: str
    ) -> None:
        """A discovered config with auto_update: false suppresses the check."""
        _config(tmp_path / "home" / ".config" / "buvis", auto_update=False, name=filename)

        result, mock_update = _invoke([], settings_class)

        assert result.exit_code == 0
        mock_update.assert_not_called()

    def test_suppressed_check_leaves_updater_state_untouched(self, tmp_path: Path) -> None:
        """A suppressed check neither creates nor modifies updater.json."""
        state_dir = tmp_path / "home" / ".config" / "buvis"
        _config(state_dir, auto_update=False)
        state = state_dir / "updater.json"
        state.write_text('{"sentinel": 1}')
        before = (state.read_bytes(), state.stat().st_mtime_ns)
        absent = tmp_path / "home" / ".local" / ".config" / "buvis" / "updater.json"

        _, mock_update = _invoke([])

        # The call count is the real suppression signal; the file assertions
        # below only add that nothing else on the path writes updater state.
        mock_update.assert_not_called()
        assert (state.read_bytes(), state.stat().st_mtime_ns) == before
        assert not absent.exists()


class TestRobustness:
    """Bad config or a failing updater never break the command."""

    def test_malformed_config_skips_check_without_crashing(self, tmp_path: Path) -> None:
        """An unparsable config file degrades the check; --help still exits 0."""
        config = tmp_path / "bad.yaml"
        config.write_text("auto_update: [unclosed\n")

        result, mock_update = _invoke(["--config", str(config), "--help"])

        assert result.exit_code == 0
        mock_update.assert_not_called()

    def test_raising_update_check_keeps_exit_code(self) -> None:
        """check_and_update raising does not change the command's exit code."""
        ran: list[bool] = []

        @click.command()
        @buvis_options
        def cmd() -> None:
            ran.append(True)

        with patch("buvis.pybase.updater.check_and_update", side_effect=RuntimeError("boom")) as mock_update:
            result = CliRunner().invoke(cmd, [])

        assert result.exit_code == 0
        assert ran == [True]
        mock_update.assert_called_once()

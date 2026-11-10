from __future__ import annotations

import os

import pytest
from braid.cli import cli as braid_cli
from braid.settings import BraidSettings
from buvis.pybase.adapters import console
from buvis.pybase.configuration import ConfigResolver, ConfigurationError, ConfigurationLoader, GlobalSettings
from click.testing import CliRunner
from rich.console import Console
from sysup.cli import cli as sysup_cli


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    for name in list(os.environ):
        if name.startswith("BUVIS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path / "override"))
    monkeypatch.setenv("BUVIS_DEV_MODE", "1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(console, "console", Console(width=240, color_system=None))


class TestConfigurationErrors:
    @pytest.mark.parametrize("content", ["scalar", "[one]", "[]", "false", "0", '""', "null"])
    def test_loader_rejects_non_mapping_roots(self, tmp_path, content):
        path = tmp_path / "invalid.yaml"
        path.write_text(content)
        with pytest.raises(ConfigurationError, match="mapping") as error:
            ConfigurationLoader.load_yaml(path)
        assert str(path) in str(error.value)

    @pytest.mark.parametrize("content", ["", "# empty config\n", "{}"])
    def test_empty_configs_remain_valid(self, tmp_path, content):
        path = tmp_path / "empty.yaml"
        path.write_text(content)
        assert ConfigurationLoader.load_yaml(path) == {}

    @pytest.mark.parametrize(
        "tool,command,args,exit_code",
        [
            ("braid", braid_cli, ["--check"], 2),
            ("sysup", sysup_cli, ["--list"], 1),
        ],
    )
    @pytest.mark.parametrize("layer", ["shared", "local", "override", "explicit"])
    @pytest.mark.parametrize(
        "content,diagnostic",
        [
            ("debug: [unclosed", "YAML"),
            ("debug: not-a-bool", "debug"),
            ("scalar", "mapping"),
        ],
    )
    def test_cli_renders_config_error(self, tmp_path, tool, command, args, exit_code, layer, content, diagnostic):
        directories = {
            "shared": tmp_path / "home/.config/buvis",
            "local": tmp_path / "home/.local/.config/buvis",
            "override": tmp_path / "override",
            "explicit": tmp_path,
        }
        path = directories[layer] / f"buvis-{tool}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        options = ["--config", str(path)] if layer == "explicit" else []
        result = CliRunner().invoke(command, [*options, *args])
        assert result.exit_code == exit_code
        assert isinstance(result.exception, SystemExit)
        assert "Traceback" not in result.output
        assert str(path) in result.output
        assert diagnostic in result.output

    @pytest.mark.parametrize("command,args,exit_code", [(braid_cli, ["--check"], 2), (sysup_cli, ["--list"], 1)])
    def test_missing_variable_names_source(self, tmp_path, command, args, exit_code):
        path = tmp_path / "home/.local/.config/buvis/buvis.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("debug: ${BUVIS_MISSING_FOR_TEST}\n")
        result = CliRunner().invoke(command, args)
        assert result.exit_code == exit_code
        assert isinstance(result.exception, SystemExit)
        assert str(path) in result.output
        assert "BUVIS_MISSING_FOR_TEST" in result.output

    def test_validation_names_offending_layer(self, tmp_path):
        shared = tmp_path / "home/.config/buvis/buvis.yaml"
        shared.parent.mkdir(parents=True)
        shared.write_text("debug: not-a-bool\n")
        local = tmp_path / "home/.local/.config/buvis/buvis.yaml"
        local.parent.mkdir(parents=True)
        local.write_text("log_level: WARNING\n")
        with pytest.raises(ConfigurationError) as error:
            ConfigResolver().resolve(GlobalSettings)
        assert str(shared) in str(error.value)
        assert str(local) not in str(error.value)

    def test_nested_validation_names_offending_layer(self, tmp_path):
        shared = tmp_path / "home/.config/buvis/buvis.yaml"
        shared.parent.mkdir(parents=True)
        shared.write_text("adapters: {jira: invalid}\n")
        local = tmp_path / "home/.local/.config/buvis/buvis.yaml"
        local.parent.mkdir(parents=True)
        local.write_text("adapters: {ollama: {}}\n")
        with pytest.raises(ConfigurationError) as error:
            ConfigResolver().resolve(GlobalSettings)
        assert str(shared) in str(error.value)
        assert str(local) not in str(error.value)

    def test_invalid_environment_collection_is_rendered(self, monkeypatch):
        monkeypatch.setenv("BUVIS_BRAID_SOURCES", "[invalid-json")
        result = CliRunner().invoke(braid_cli, ["--check"])
        assert result.exit_code == 2
        assert isinstance(result.exception, SystemExit)
        assert "sources" in result.output
        assert "Traceback" not in result.output

    def test_list_directive_retains_contributing_source(self, tmp_path):
        shared = tmp_path / "home/.config/buvis/buvis-braid.yaml"
        shared.parent.mkdir(parents=True)
        shared.write_text("sources: [{}]\n")
        local = tmp_path / "home/.local/.config/buvis/buvis-braid.yaml"
        local.parent.mkdir(parents=True)
        local.write_text("sources+: [/valid]\n")
        with pytest.raises(ConfigurationError) as error:
            ConfigResolver().resolve(BraidSettings)
        assert str(shared) in str(error.value)

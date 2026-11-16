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
    @pytest.mark.parametrize("defect", ["unreadable", "non-utf8"])
    def test_unreadable_config_is_rendered_not_raised(self, tmp_path, command, args, exit_code, defect):
        name = "buvis-braid.yaml" if command is braid_cli else "buvis-sysup.yaml"
        path = tmp_path / "home/.config/buvis" / name
        path.parent.mkdir(parents=True)
        if defect == "unreadable":
            if os.geteuid() == 0:
                pytest.skip("root reads mode-000 files")
            path.write_text("debug: true\n")
            path.chmod(0o000)
        else:
            path.write_bytes(b"debug: \xff\xfe\n")
        result = CliRunner().invoke(command, args)
        assert result.exit_code == exit_code
        assert isinstance(result.exception, SystemExit)
        assert str(path) in result.output
        assert "cannot read config" in result.output

    @pytest.mark.parametrize("command,args,exit_code", [(braid_cli, ["--check"], 2), (sysup_cli, ["--list"], 1)])
    @pytest.mark.parametrize("defect", ["missing", "directory", "dangling-link", "unreadable"])
    def test_bad_explicit_config_path_is_rendered_by_the_console(self, tmp_path, command, args, exit_code, defect):
        path = tmp_path / "custom.yaml"
        if defect == "directory":
            path.mkdir()
        elif defect == "dangling-link":
            path.symlink_to("nowhere.yaml")
        elif defect == "unreadable":
            if os.geteuid() == 0:
                pytest.skip("root reads mode-000 files")
            path.write_text("debug: true\n")
            path.chmod(0o000)
        result = CliRunner().invoke(command, ["--config", str(path), *args])
        assert result.exit_code == exit_code
        assert "Usage:" not in result.output
        assert str(path) in result.output
        assert "cannot read config" in result.output

    @pytest.mark.parametrize("command,args,exit_code", [(braid_cli, ["--check"], 2), (sysup_cli, ["--list"], 1)])
    @pytest.mark.parametrize(
        "value", ["", "missing-dir", "a-file", "n" * 300], ids=["empty", "missing", "file", "long"]
    )
    def test_bad_config_dir_is_rendered_by_the_console(self, tmp_path, command, args, exit_code, value):
        (tmp_path / "a-file").write_text("debug: true\n")
        # The cwd holds a valid config: an empty value must not fall back to it.
        (tmp_path / "config.yaml").write_text("debug: true\n")
        result = CliRunner().invoke(command, ["--config-dir", value, *args])
        assert result.exit_code == exit_code
        assert "Usage:" not in result.output
        assert f"--config-dir {value!r}: not a directory" in result.output

    @pytest.mark.parametrize("command,args,exit_code", [(braid_cli, ["--check"], 2), (sysup_cli, ["--list"], 1)])
    def test_dangling_discovered_config_link_is_rendered(self, tmp_path, command, args, exit_code):
        name = "buvis-braid.yaml" if command is braid_cli else "buvis-sysup.yaml"
        path = tmp_path / "home/.local/.config/buvis" / name
        path.parent.mkdir(parents=True)
        path.symlink_to("nowhere.yaml")
        result = CliRunner().invoke(command, args)
        assert result.exit_code == exit_code
        assert str(path) in result.output
        assert "cannot read config" in result.output

    @pytest.mark.parametrize("command,args,exit_code", [(braid_cli, ["--check"], 2), (sysup_cli, ["--list"], 1)])
    def test_explicit_yaml_error_names_file_once(self, tmp_path, command, args, exit_code):
        path = tmp_path / "custom.yaml"
        path.write_text("debug: [unclosed")
        result = CliRunner().invoke(command, ["--config", str(path), *args])
        assert result.exit_code == exit_code
        assert result.output.count(str(path)) == 1
        assert "<unicode string>" not in result.output

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

    def test_log_level_from_yaml_and_env_is_case_insensitive(self, tmp_path, monkeypatch):
        shared = tmp_path / "home/.config/buvis/config.yaml"
        shared.parent.mkdir(parents=True)
        shared.write_text("log_level: warning\n")
        assert ConfigResolver().resolve(GlobalSettings).log_level == "WARNING"
        monkeypatch.setenv("BUVIS_LOG_LEVEL", "debug")
        assert ConfigResolver().resolve(GlobalSettings).log_level == "DEBUG"

    def test_set_env_var_beats_yaml_even_at_the_default_value(self, tmp_path, monkeypatch):
        shared = tmp_path / "home/.config/buvis/config.yaml"
        shared.parent.mkdir(parents=True)
        shared.write_text("debug: true\nauto_update: false\n")
        monkeypatch.setenv("BUVIS_DEBUG", "false")
        monkeypatch.setenv("buvis_auto_update", "true")
        resolver = ConfigResolver()
        settings = resolver.resolve(GlobalSettings)
        assert settings.debug is False
        assert settings.auto_update is True
        assert resolver.sources["debug"].value == "env"
        assert resolver.sources["auto_update"].value == "env"

    def test_yaml_still_applies_when_only_another_field_is_set_in_env(self, tmp_path, monkeypatch):
        shared = tmp_path / "home/.config/buvis/config.yaml"
        shared.parent.mkdir(parents=True)
        shared.write_text("debug: true\nadapters: {jira: {server: https://example.test}}\n")
        monkeypatch.setenv("BUVIS_LOG_LEVEL", "ERROR")
        settings = ConfigResolver().resolve(GlobalSettings)
        assert settings.debug is True
        assert settings.adapters == {"jira": {"server": "https://example.test"}}
        assert settings.log_level == "ERROR"

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


class TestDocumentedNestedEnvironment:
    def test_photo_prefix_joins_field_before_nested_delimiter(self, monkeypatch):
        from buvis.pybase.configuration import ToolSettings
        from pydantic_settings import SettingsConfigDict

        class DatabaseSettings(ToolSettings):
            host: str = "localhost"

        class PhotoSettings(GlobalSettings):
            model_config = SettingsConfigDict(env_prefix="BUVIS_PHOTO_", env_nested_delimiter="__")
            db: DatabaseSettings = DatabaseSettings()

        monkeypatch.setenv("BUVIS_PHOTO__DB__HOST", "wrong.example")
        assert ConfigResolver().resolve(PhotoSettings).db.host == "localhost"
        monkeypatch.setenv("BUVIS_PHOTO_DB__HOST", "prod.db.local")
        assert ConfigResolver().resolve(PhotoSettings).db.host == "prod.db.local"

    def test_documentation_uses_the_verified_nested_prefix(self):
        from pathlib import Path

        doc = Path(__file__).resolve().parents[4] / "docs/source/configuration.rst"
        assert "BUVIS_PHOTO__" not in doc.read_text()

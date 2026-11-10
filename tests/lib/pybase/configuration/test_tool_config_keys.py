from __future__ import annotations

import os
from pathlib import Path

import pytest
from backup.settings import BackupSettings
from braid.cli import cli
from braid.settings import BraidSettings
from buvis.pybase.adapters import console
from buvis.pybase.configuration import ConfigResolver, ConfigurationError, GlobalSettings
from click.testing import CliRunner
from pydantic_settings import SettingsConfigDict
from rich.console import Console
from sysup.settings import SysupSettings


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


class TestToolConfigKeys:
    @pytest.mark.parametrize("key", ["srouces", "sorces+", "polcies-", "config_root"])
    @pytest.mark.parametrize("layer", ["shared-dir", "local-dir", "override", "explicit"])
    def test_rejects_unknown_tool_keys_before_projection(self, tmp_path, key, layer):
        directories = {
            "shared-dir": tmp_path / "home/.config/buvis",
            "local-dir": tmp_path / "home/.local/.config/buvis",
            "override": tmp_path / "override",
            "explicit": tmp_path,
        }
        path = directories[layer] / ("candidate.yaml" if layer == "explicit" else "buvis-braid.yaml")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{key}: [/unused]\n")
        with pytest.raises(ConfigurationError, match=key.replace("+", r"\+")) as error:
            ConfigResolver().resolve(BraidSettings, config_path=path if layer == "explicit" else None)
        assert str(path) in str(error.value)
        assert "unknown" in str(error.value)

    @pytest.mark.parametrize("filename", ["config.yaml", "buvis.yaml"])
    @pytest.mark.parametrize("explicit", [False, True])
    def test_shared_config_keeps_other_tool_namespaces(self, tmp_path, filename, explicit):
        path = tmp_path / "home/.config/buvis" / filename
        path.parent.mkdir(parents=True)
        path.write_text(
            "debug: true\nadapters: {jira: {server: https://example.test}}\n"
            "sysup: {commands: {example: {steps: [true]}}}\nbim: {path_zettelkasten: /notes}\n"
            "sources+: [/shared-skills]\n"
        )
        settings = ConfigResolver().resolve(BraidSettings, config_path=path if explicit else None)
        assert settings.debug is True
        assert settings.adapters == {"jira": {"server": "https://example.test"}}
        assert settings.sources == (Path("/shared-skills"),)
        assert not hasattr(settings, "sysup")

    def test_other_tool_files_are_not_validated(self, tmp_path):
        path = tmp_path / "home/.config/buvis/buvis-sysup.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("commands: [unclosed")
        assert ConfigResolver().resolve(BraidSettings).sources == ()

    def test_known_directives_and_global_fields_remain_valid(self, tmp_path):
        path = tmp_path / "candidate.yaml"
        path.write_text("debug: true\nsources+: [/skills]\npolicies: [/drop]\npolicies+: [/keep]\npolicies-: [/drop]")
        settings = ConfigResolver().resolve(BraidSettings, config_path=path)
        assert settings.debug is True
        assert settings.sources == (Path("/skills"),)
        assert settings.policies == (Path("/keep"),)

    def test_extra_ignore_retains_permissive_behavior(self, tmp_path):
        class LenientSettings(GlobalSettings):
            model_config = SettingsConfigDict(env_prefix="BUVIS_LENIENT_", extra="ignore")

        path = tmp_path / "candidate.yaml"
        path.write_text("unknown: anything\ndebug: true")
        assert ConfigResolver().resolve(LenientSettings, config_path=path).debug is True

    @pytest.mark.parametrize(
        "settings_class,content",
        [
            (SysupSettings, "commands: {}\nprime+: [brew]\nntfy: {}\nexpiry: {}"),
            (BackupSettings, "instances: {}\nexcludes+: [cache]"),
        ],
    )
    def test_separately_validated_tool_plans_are_preserved(self, tmp_path, settings_class, content):
        path = tmp_path / "candidate.yaml"
        path.write_text(content)
        assert ConfigResolver().resolve(settings_class, config_path=path) == settings_class()

    def test_cli_rejects_removed_key_with_exit_two(self, tmp_path):
        path = tmp_path / "candidate.yaml"
        path.write_text("config_root: /retired")
        result = CliRunner().invoke(cli, ["--config", str(path), "--check"])
        assert result.exit_code == 2
        assert "config_root" in result.output
        assert str(path) in result.output
        assert "no skill sources configured" not in result.output

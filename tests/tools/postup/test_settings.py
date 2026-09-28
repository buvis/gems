from __future__ import annotations

from pathlib import Path

from buvis.pybase.configuration import ConfigResolver
from postup.settings import PostupSettings, default_out_dir


class TestPostupSettingsDefaults:
    def test_out_dir_defaults_to_xdg(self, monkeypatch):
        monkeypatch.delenv("BUVIS_POSTUP_OUT_DIR", raising=False)
        settings = PostupSettings()
        assert settings.out_dir == ""  # unset by default
        assert settings.resolved_out_dir == default_out_dir()
        assert str(settings.resolved_out_dir).endswith("/.local/share/postup")

    def test_configured_out_dir_is_used(self):
        settings = PostupSettings(out_dir="/data/postup")
        assert settings.resolved_out_dir == Path("/data/postup")

    def test_empty_roots_and_excludes_by_default(self):
        settings = PostupSettings()
        assert settings.roots == []
        assert settings.excludes == []
        assert settings.model is None


class TestEnvPrefix:
    def test_env_prefix_overrides_out_dir(self, monkeypatch):
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", "/tmp/postup-out")
        settings = PostupSettings()
        assert settings.out_dir == "/tmp/postup-out"

    def test_env_prefix_parses_json_list(self, monkeypatch):
        monkeypatch.setenv("BUVIS_POSTUP_ROOTS", '["/a", "/b"]')
        settings = PostupSettings()
        assert settings.roots == ["/a", "/b"]


class TestConfigLayering:
    def test_config_file_overrides_defaults(self, tmp_path, monkeypatch):
        monkeypatch.delenv("BUVIS_POSTUP_OUT_DIR", raising=False)
        config = tmp_path / "postup.yaml"
        config.write_text("roots:\n  - /work/src\nout_dir: /data/postup\nmodel: claude-sonnet\n")

        settings = ConfigResolver().resolve(PostupSettings, config_path=config)

        assert settings.roots == ["/work/src"]
        assert settings.out_dir == "/data/postup"
        assert settings.model == "claude-sonnet"

    def test_env_wins_over_config(self, tmp_path, monkeypatch):
        config = tmp_path / "postup.yaml"
        config.write_text("out_dir: /from/config\n")
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", "/from/env")

        settings = ConfigResolver().resolve(PostupSettings, config_path=config)
        assert settings.out_dir == "/from/env"

    def test_cli_override_wins(self, tmp_path):
        config = tmp_path / "postup.yaml"
        config.write_text("debug: false\n")
        settings = ConfigResolver().resolve(PostupSettings, config_path=config, cli_overrides={"debug": True})
        assert settings.debug is True

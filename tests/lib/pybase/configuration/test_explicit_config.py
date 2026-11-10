from __future__ import annotations

import os
from pathlib import Path

import pytest
from braid.settings import BraidSettings
from buvis.pybase.configuration import ConfigResolver, ConfigurationError


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    for name in list(os.environ):
        if name.startswith("BUVIS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)


class TestExplicitConfig:
    @pytest.mark.parametrize(
        "content,field,expected",
        [
            ("sources+: [/skills]", "sources", (Path("/skills"),)),
            ("policies+: [/keep]", "policies", (Path("/keep"),)),
            ("policies: [/drop, /keep]\npolicies-: [/drop]", "policies", (Path("/keep"),)),
            ('sources: ["${HOME}/skills"]', "sources", None),
        ],
    )
    def test_explicit_uses_discovered_pipeline(self, tmp_path, content, field, expected):
        path = tmp_path / "candidate.yaml"
        path.write_text(content)
        resolver = ConfigResolver()
        explicit = resolver.resolve(BraidSettings, config_path=path)
        discovered = tmp_path / "home/.local/.config/buvis/buvis-braid.yaml"
        discovered.parent.mkdir(parents=True)
        discovered.write_text(content)
        settings = resolver.resolve(BraidSettings)
        assert getattr(explicit, field) == getattr(settings, field)
        assert getattr(explicit, field) == (expected or (tmp_path / "home/skills",))

    def test_explicit_remains_exclusive(self, tmp_path, monkeypatch):
        for directory in (tmp_path, tmp_path / "home/.config/buvis", tmp_path / "home/.local/.config/buvis"):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "buvis-braid.yaml").write_text("sources: [unclosed")
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        path = tmp_path / "candidate.yaml"
        path.write_text("sources+: [/only-explicit]\n")
        settings = ConfigResolver().resolve(BraidSettings, config_path=path)
        assert settings.sources == (Path("/only-explicit"),)

    def test_explicit_missing_variable_names_file(self, tmp_path):
        path = tmp_path / "candidate.yaml"
        path.write_text('sources: ["${BUVIS_MISSING_FOR_TEST}/skills"]')
        with pytest.raises(ConfigurationError, match="BUVIS_MISSING_FOR_TEST") as error:
            ConfigResolver().resolve(BraidSettings, config_path=path)
        assert str(path) in str(error.value)

    def test_explicit_preserves_escaping_and_defaults(self, tmp_path):
        path = tmp_path / "candidate.yaml"
        path.write_text('sources: ["/${BUVIS_MISSING_FOR_TEST:-fallback}", "/$${LITERAL}"]')
        settings = ConfigResolver().resolve(BraidSettings, config_path=path)
        assert settings.sources == (Path("/fallback"), Path("/${LITERAL}"))

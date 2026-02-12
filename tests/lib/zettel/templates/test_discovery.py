from __future__ import annotations

import yaml
from buvis.pybase.zettel.domain.templates import (
    discover_templates,
    discover_yaml_templates,
)
from buvis.pybase.zettel.domain.templates.yaml_template import YamlTemplate
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


class TestDiscoverYamlTemplates:
    def test_loads_from_config_dir(self, tmp_path, monkeypatch):
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "meeting.yaml").write_text(
            yaml.dump({"name": "meeting", "metadata": {"type": "meeting"}}),
        )
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))

        result = discover_yaml_templates({}, python_eval)
        assert "meeting" in result
        assert isinstance(result["meeting"], YamlTemplate)

    def test_yaml_overrides_python(self, tmp_path, monkeypatch):
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "note.yaml").write_text(
            yaml.dump({"name": "note", "metadata": {"type": "custom-note"}}),
        )
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))

        from buvis.pybase.zettel.domain.templates.note import NoteTemplate

        base = {"note": NoteTemplate()}
        result = discover_yaml_templates(base, python_eval)
        assert isinstance(result["note"], YamlTemplate)

    def test_extends_resolves(self, tmp_path, monkeypatch):
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "standup.yaml").write_text(
            yaml.dump(
                {
                    "name": "standup",
                    "extends": "note",
                    "metadata": {"type": "standup"},
                }
            ),
        )
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))

        from buvis.pybase.zettel.domain.templates.note import NoteTemplate

        base = {"note": NoteTemplate()}
        result = discover_yaml_templates(base, python_eval)
        assert "standup" in result
        data = result["standup"].build_data({"title": "Daily"})
        assert data.metadata["type"] == "standup"

    def test_skips_invalid_yaml(self, tmp_path, monkeypatch):
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "bad.yaml").write_text("not: valid: yaml: [")
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))

        result = discover_yaml_templates({}, python_eval)
        assert "bad" not in result

    def test_skips_yaml_without_name(self, tmp_path, monkeypatch):
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "noname.yaml").write_text(yaml.dump({"type": "x"}))
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))

        result = discover_yaml_templates({}, python_eval)
        assert len(result) == 0

    def test_higher_priority_overrides(self, tmp_path, monkeypatch):
        # BUVIS_CONFIG_DIR takes priority over ~/.config/buvis
        high = tmp_path / "high"
        low = tmp_path / "low"
        for d in (high, low):
            (d / "templates").mkdir(parents=True)

        (low / "templates" / "t.yaml").write_text(
            yaml.dump({"name": "t", "metadata": {"source": "low"}}),
        )
        (high / "templates" / "t.yaml").write_text(
            yaml.dump({"name": "t", "metadata": {"source": "high"}}),
        )
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(high))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(low))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))

        result = discover_yaml_templates({}, python_eval)
        data = result["t"].build_data({"title": "X"})
        assert data.metadata["source"] == "high"


class TestDiscoverTemplates:
    def test_includes_python_templates(self):
        templates = discover_templates(python_eval)
        assert "note" in templates
        assert "project" in templates

    def test_includes_yaml_templates(self, tmp_path, monkeypatch):
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "custom.yaml").write_text(
            yaml.dump({"name": "custom", "metadata": {"type": "custom"}}),
        )
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))

        templates = discover_templates(python_eval)
        assert "note" in templates
        assert "custom" in templates

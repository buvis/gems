from __future__ import annotations

import logging
from pathlib import Path

import yaml
from buvis.pybase.zettel.domain.templates import Hook
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.persistence.template_loader import (
    _create_project_dir,
    _scan_yaml_dir,
    discover_yaml_templates,
    run_template_hooks,
)
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


class TestScanYamlDir:
    def test_nonexistent_dir_does_nothing(self, tmp_path):
        found: dict = {}
        _scan_yaml_dir(tmp_path / "nope", {}, found, python_eval)
        assert found == {}

    def test_extends_resolves_from_found(self, tmp_path):
        """extends can reference a template already in found dict, not just base_templates."""
        (tmp_path / "base.yaml").write_text(
            yaml.dump({"name": "base", "metadata": {"type": "base"}}),
        )
        (tmp_path / "child.yaml").write_text(
            yaml.dump({"name": "child", "extends": "base", "metadata": {"type": "child"}}),
        )

        found: dict = {}
        _scan_yaml_dir(tmp_path, {}, found, python_eval)
        assert "base" in found
        assert "child" in found

    def test_skips_non_dict_yaml(self, tmp_path):
        (tmp_path / "list.yaml").write_text(yaml.dump(["a", "b"]))
        found: dict = {}
        _scan_yaml_dir(tmp_path, {}, found, python_eval)
        assert found == {}

    def test_skips_yaml_without_name(self, tmp_path):
        (tmp_path / "noname.yaml").write_text(yaml.dump({"type": "x"}))
        found: dict = {}
        _scan_yaml_dir(tmp_path, {}, found, python_eval)
        assert found == {}

    def test_logs_warning_on_bad_yaml(self, tmp_path, caplog):
        (tmp_path / "bad.yaml").write_text("not: valid: yaml: [")
        found: dict = {}
        with caplog.at_level(logging.WARNING):
            _scan_yaml_dir(tmp_path, {}, found, python_eval)
        assert found == {}
        assert "Failed to load template" in caplog.text


class TestDiscoverYamlTemplates:
    def test_bundled_templates_loaded(self):
        result = discover_yaml_templates({}, python_eval)
        # bundled dir may have templates; at minimum the function runs without error
        assert isinstance(result, dict)


class TestCreateProjectDir:
    def test_creates_dir_and_sets_metadata(self, tmp_path):
        zk_path = tmp_path / "zettelkasten" / "notes"
        zk_path.mkdir(parents=True)
        data = ZettelData(metadata={"id": "20240115"})
        _create_project_dir(data, zk_path)

        project_dir = tmp_path / "zettelkasten" / "projects" / "20240115"
        assert project_dir.is_dir()
        assert "resources" in data.metadata
        assert "20240115" in data.metadata["resources"]

    def test_missing_id_uses_unknown(self, tmp_path):
        zk_path = tmp_path / "zettelkasten" / "notes"
        zk_path.mkdir(parents=True)
        data = ZettelData(metadata={})
        _create_project_dir(data, zk_path)

        project_dir = tmp_path / "zettelkasten" / "projects" / "unknown"
        assert project_dir.is_dir()

    def test_idempotent(self, tmp_path):
        zk_path = tmp_path / "zettelkasten" / "notes"
        zk_path.mkdir(parents=True)
        data = ZettelData(metadata={"id": "abc"})
        _create_project_dir(data, zk_path)
        _create_project_dir(data, zk_path)
        assert (tmp_path / "zettelkasten" / "projects" / "abc").is_dir()


class TestRunTemplateHooks:
    def test_known_hook_executes(self, tmp_path):
        zk_path = tmp_path / "zettelkasten" / "notes"
        zk_path.mkdir(parents=True)
        data = ZettelData(metadata={"id": "proj1"})
        hooks = [Hook(name="create_project_dir")]
        run_template_hooks(hooks, data, zk_path)

        assert (tmp_path / "zettelkasten" / "projects" / "proj1").is_dir()
        assert "resources" in data.metadata

    def test_unknown_hook_logs_warning(self, caplog):
        data = ZettelData(metadata={})
        hooks = [Hook(name="nonexistent_hook")]
        with caplog.at_level(logging.WARNING):
            run_template_hooks(hooks, data, Path("/dummy"))
        assert "No hook handler registered for 'nonexistent_hook'" in caplog.text

    def test_empty_hooks_list(self):
        data = ZettelData(metadata={})
        run_template_hooks([], data, Path("/dummy"))
        # no error, nothing happens

    def test_multiple_hooks(self, tmp_path, caplog):
        zk_path = tmp_path / "zettelkasten" / "notes"
        zk_path.mkdir(parents=True)
        data = ZettelData(metadata={"id": "multi"})
        hooks = [Hook(name="create_project_dir"), Hook(name="unknown")]
        with caplog.at_level(logging.WARNING):
            run_template_hooks(hooks, data, zk_path)
        assert (tmp_path / "zettelkasten" / "projects" / "multi").is_dir()
        assert "No hook handler registered for 'unknown'" in caplog.text

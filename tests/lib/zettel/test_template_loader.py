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
    def test_creates_id_slug_folder_under_path_projects_and_links_it(self, tmp_path):
        projects = tmp_path / "10-projects"
        projects.mkdir()
        data = ZettelData(metadata={"id": 20240115120000, "title": "Probe run"})

        warning = _create_project_dir(data, tmp_path / "notes", projects)

        project_dir = projects / "20240115120000-probe-run"
        assert warning is None
        assert project_dir.is_dir()
        assert data.metadata["resources"] == f"[project resources]({project_dir.as_uri()})"

    def test_project_dir_skipped_when_root_missing(self, tmp_path):
        projects = tmp_path / "absent"
        data = ZettelData(metadata={"id": 1, "title": "Probe"})

        warning = _create_project_dir(data, tmp_path / "notes", projects)

        assert not projects.exists()
        assert data.metadata["resources"] == f"[project resources]({(projects / '1-probe').as_uri()})"
        assert warning == f"project resources folder {projects / '1-probe'} not created: {projects} does not exist"

    def test_unset_root_skips_without_resources_link(self, tmp_path):
        data = ZettelData(metadata={"id": 1, "title": "Probe"})

        warning = _create_project_dir(data, tmp_path / "notes", None)

        assert warning == "project resources folder skipped: path_projects is not set"
        assert "resources" not in data.metadata

    def test_missing_title_and_id_still_make_a_folder(self, tmp_path):
        data = ZettelData(metadata={})
        _create_project_dir(data, tmp_path / "notes", tmp_path)
        _create_project_dir(data, tmp_path / "notes", tmp_path)
        assert (tmp_path / "unknown").is_dir()


class TestRunTemplateHooks:
    def test_known_hook_executes_and_reports_no_warning(self, tmp_path):
        projects = tmp_path / "projects"
        projects.mkdir()
        data = ZettelData(metadata={"id": "proj1", "title": "Multi"})

        warnings = run_template_hooks(
            [Hook(name="create_project_dir")], data, tmp_path / "notes", path_projects=projects
        )

        assert warnings == []
        assert (projects / "proj1-multi").is_dir()
        assert "resources" in data.metadata

    def test_set_parent_reference_links_the_note_itself(self, tmp_path):
        data = ZettelData(metadata={"id": 20240115120000, "title": "Probe"})

        run_template_hooks([Hook(name="set_parent_reference")], data, tmp_path / "notes")

        assert data.reference == {"parent": "[[notes/20240115120000|Probe]]"}

    def test_set_illustration_link_fills_id_in_first_section_only(self):
        data = ZettelData(
            metadata={"id": 20240115120000},
            sections=[("# T", "![T]({id}.svg)"), ("# Text Elements", "{id} stays")],
        )

        run_template_hooks([Hook(name="set_illustration_link")], data, Path("/dummy"))

        assert data.sections == [("# T", "![T](20240115120000.svg)"), ("# Text Elements", "{id} stays")]

    def test_unknown_hook_logs_warning(self, caplog):
        data = ZettelData(metadata={})
        hooks = [Hook(name="nonexistent_hook")]
        with caplog.at_level(logging.WARNING):
            assert run_template_hooks(hooks, data, Path("/dummy")) == []
        assert "No hook handler registered for 'nonexistent_hook'" in caplog.text

    def test_empty_hooks_list(self):
        data = ZettelData(metadata={})
        assert run_template_hooks([], data, Path("/dummy")) == []

    def test_multiple_hooks_collect_warnings_and_log_unknown(self, tmp_path, caplog):
        projects = tmp_path / "absent"
        data = ZettelData(metadata={"id": "multi", "title": "Multi"})
        hooks = [Hook(name="create_project_dir"), Hook(name="unknown")]

        with caplog.at_level(logging.WARNING):
            warnings = run_template_hooks(hooks, data, tmp_path / "notes", path_projects=projects)

        assert warnings == [
            f"project resources folder {projects / 'multi-multi'} not created: {projects} does not exist"
        ]
        assert "No hook handler registered for 'unknown'" in caplog.text

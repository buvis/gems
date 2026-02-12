from __future__ import annotations

import inspect
import types
from pathlib import Path

import pytest

from buvis.pybase.configuration.exceptions import MissingEnvVarError
from buvis.pybase.configuration.loader import (
    _ENV_PATTERN,
    ConfigurationLoader,
    _substitute,
)


class TestConfigurationLoaderScaffold:
    def test_class_exists(self) -> None:
        assert inspect.isclass(ConfigurationLoader)

    def test_find_config_files_exists(self) -> None:
        assert hasattr(ConfigurationLoader, "find_config_files")
        assert isinstance(ConfigurationLoader.find_config_files, types.FunctionType)


class TestFindConfigFiles:
    """Tests for find_config_files method."""

    def test_no_files_returns_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty directory returns empty list."""
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        result = ConfigurationLoader.find_config_files()

        assert result == []

    def test_single_buvis_yaml_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Single buvis.yaml is returned."""
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        config = tmp_path / "buvis.yaml"
        config.write_text("key: value\n")

        result = ConfigurationLoader.find_config_files()

        assert len(result) == 1
        assert result[0] == config.resolve()

    def test_tool_specific_file_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tool-specific config file is found."""
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        tool_config = tmp_path / "buvis-cli.yaml"
        tool_config.write_text("tool: true\n")

        result = ConfigurationLoader.find_config_files(tool_name="cli")

        assert any("buvis-cli.yaml" in str(p) for p in result)

    def test_both_buvis_and_tool_config_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Both buvis.yaml and tool-specific are found."""
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        (tmp_path / "buvis.yaml").write_text("base: true\n")
        (tmp_path / "buvis-mytool.yaml").write_text("tool: true\n")

        result = ConfigurationLoader.find_config_files(tool_name="mytool")

        assert len(result) == 2

    def test_permission_denied_skipped(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Permission error skips file without crashing."""
        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        config = tmp_path / "buvis.yaml"
        config.write_text("key: value\n")

        original_is_file = Path.is_file

        def mock_is_file(self):
            if self == config:
                raise PermissionError("Access denied")
            return original_is_file(self)

        monkeypatch.setattr(Path, "is_file", mock_is_file)

        result = ConfigurationLoader.find_config_files()

        assert result == []


class TestIsSafePath:
    """Tests for _is_safe_path security validation."""

    def test_regular_file_is_safe(self, tmp_path: Path) -> None:
        """Normal file under allowed base is safe."""
        file = tmp_path / "config.yaml"
        file.touch()

        assert ConfigurationLoader._is_safe_path(file, [tmp_path]) is True

    def test_symlink_within_allowed_is_safe(self, tmp_path: Path) -> None:
        """Symlink pointing within allowed base is safe."""
        target = tmp_path / "target.yaml"
        target.touch()
        link = tmp_path / "link.yaml"
        link.symlink_to(target)

        assert ConfigurationLoader._is_safe_path(link, [tmp_path]) is True

    def test_symlink_outside_is_unsafe(self, tmp_path: Path) -> None:
        """Symlink pointing outside allowed base is unsafe."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "target.yaml"
        target.touch()
        link = allowed / "escape.yaml"
        link.symlink_to(target)

        assert ConfigurationLoader._is_safe_path(link, [allowed]) is False

    def test_broken_symlink_within_base_is_safe(self, tmp_path: Path) -> None:
        """Broken symlink within allowed base is path-safe (existence checked elsewhere)."""
        link = tmp_path / "broken.yaml"
        link.symlink_to(tmp_path / "nonexistent")

        # Path-safe because resolved target is under allowed base
        # (find_config_files filters non-existent files via is_file())
        assert ConfigurationLoader._is_safe_path(link, [tmp_path]) is True

    def test_multiple_allowed_bases(self, tmp_path: Path) -> None:
        """File is safe if under any allowed base."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        file = dir2 / "config.yaml"
        file.touch()

        assert ConfigurationLoader._is_safe_path(file, [dir1, dir2]) is True


class TestEnvPattern:
    def test_matches_variable(self) -> None:
        match = _ENV_PATTERN.fullmatch("${VAR}")
        assert match is not None
        assert match.group(1) == "VAR"
        assert match.group(2) is None

    def test_matches_variable_with_default(self) -> None:
        match = _ENV_PATTERN.fullmatch("${VAR:-default}")
        assert match is not None
        assert match.group(1) == "VAR"
        assert match.group(2) == "default"


class TestSubstitute:
    """Tests for _substitute env var replacement."""

    def test_var_set_substituted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """${VAR} with VAR set -> value substituted."""
        monkeypatch.setenv("DB_HOST", "localhost")

        result, missing = _substitute("host: ${DB_HOST}")

        assert result == "host: localhost"
        assert missing == []

    def test_var_unset_tracked_in_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """${VAR} with VAR unset -> tracked in missing list."""
        monkeypatch.delenv("UNSET_VAR", raising=False)

        result, missing = _substitute("key: ${UNSET_VAR}")

        assert result == "key: ${UNSET_VAR}"  # Kept for error msg
        assert missing == ["UNSET_VAR"]

    def test_var_unset_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """${VAR:-default} with VAR unset -> uses default."""
        monkeypatch.delenv("DB_PORT", raising=False)

        result, missing = _substitute("port: ${DB_PORT:-5432}")

        assert result == "port: 5432"
        assert missing == []

    def test_var_set_ignores_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """${VAR:-default} with VAR set -> uses VAR value."""
        monkeypatch.setenv("DB_PORT", "3306")

        result, missing = _substitute("port: ${DB_PORT:-5432}")

        assert result == "port: 3306"
        assert missing == []

    def test_nested_not_expanded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env value containing ${} is NOT re-processed."""
        monkeypatch.setenv("VAR", "${NESTED}")

        result, missing = _substitute("val: ${VAR}")

        assert result == "val: ${NESTED}"  # Literal, not expanded
        assert missing == []

    def test_multiple_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple vars in same content all substituted."""
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "5432")

        result, missing = _substitute("url: ${HOST}:${PORT}")

        assert result == "url: localhost:5432"
        assert missing == []

    def test_multiple_missing_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple missing vars all tracked."""
        monkeypatch.delenv("VAR1", raising=False)
        monkeypatch.delenv("VAR2", raising=False)

        result, missing = _substitute("a: ${VAR1}, b: ${VAR2}")

        assert missing == ["VAR1", "VAR2"]


class TestLoadYaml:
    """Tests for ConfigurationLoader.load_yaml method."""

    def test_valid_yaml_loads(self, tmp_path: Path) -> None:
        """Valid YAML file is parsed correctly."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value\nnested:\n  inner: data")

        result = ConfigurationLoader.load_yaml(yaml_file)

        assert result == {"key": "value", "nested": {"inner": "data"}}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Empty file returns empty dict."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        result = ConfigurationLoader.load_yaml(yaml_file)

        assert result == {}

    def test_comments_only_returns_empty_dict(self, tmp_path: Path) -> None:
        """File with only comments returns empty dict."""
        yaml_file = tmp_path / "comments.yaml"
        yaml_file.write_text("# This is a comment\n# Another comment")

        result = ConfigurationLoader.load_yaml(yaml_file)

        assert result == {}

    def test_env_var_substituted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """${VAR} is substituted with env value."""
        monkeypatch.setenv("DB_HOST", "localhost")
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("host: ${DB_HOST}")

        result = ConfigurationLoader.load_yaml(yaml_file)

        assert result == {"host": "localhost"}

    def test_env_var_with_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """${VAR:-default} uses default when var unset."""
        monkeypatch.delenv("DB_PORT", raising=False)
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("port: ${DB_PORT:-5432}")

        result = ConfigurationLoader.load_yaml(yaml_file)

        assert result == {"port": 5432}  # YAML parses as int

    def test_missing_required_var_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing required env var raises MissingEnvVarError."""
        monkeypatch.delenv("REQUIRED_VAR", raising=False)
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: ${REQUIRED_VAR}")

        with pytest.raises(MissingEnvVarError) as exc_info:
            ConfigurationLoader.load_yaml(yaml_file)

        assert "REQUIRED_VAR" in exc_info.value.var_names

    def test_escaped_dollar_preserved(self, tmp_path: Path) -> None:
        """$${VAR} becomes literal ${VAR} in output."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("literal: $${NOT_SUBSTITUTED}")

        result = ConfigurationLoader.load_yaml(yaml_file)

        assert result == {"literal": "${NOT_SUBSTITUTED}"}

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """Missing file raises FileNotFoundError."""
        missing = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            ConfigurationLoader.load_yaml(missing)

    def test_invalid_yaml_raises_yamlerror(self, tmp_path: Path) -> None:
        """Malformed YAML raises yaml.YAMLError."""
        import yaml

        invalid = tmp_path / "invalid.yaml"
        invalid.write_text("key: [unclosed\n  - list")

        with pytest.raises(yaml.YAMLError):
            ConfigurationLoader.load_yaml(invalid)

    def test_yamlerror_contains_line_number(self, tmp_path: Path) -> None:
        """yaml.YAMLError contains problem_mark with line info."""
        import yaml

        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("good: value\nbad: [unclosed")

        with pytest.raises(yaml.YAMLError) as exc_info:
            ConfigurationLoader.load_yaml(bad_yaml)

        assert exc_info.value.problem_mark is not None
        assert exc_info.value.problem_mark.line >= 0


class TestGetSearchPaths:
    def test_all_env_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "/custom/config")
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/xdg")

        paths = ConfigurationLoader._get_search_paths()

        assert len(paths) == 4
        assert paths[0] == Path("/custom/config")
        assert paths[1] == Path("/custom/xdg/buvis")

    def test_buvis_config_dir_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        paths = ConfigurationLoader._get_search_paths()

        # Empty BUVIS_CONFIG_DIR treated as unset, so 3 paths
        assert len(paths) == 3
        assert paths[0] == Path.home() / ".config" / "buvis"

    def test_xdg_config_home_empty_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BUVIS_CONFIG_DIR", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", "")

        paths = ConfigurationLoader._get_search_paths()

        assert paths[0] == Path.home() / ".config" / "buvis"

    def test_path_order_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "/override")
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg")

        paths = ConfigurationLoader._get_search_paths()

        assert paths[0] == Path("/override")
        assert paths[1] == Path("/xdg/buvis")
        assert paths[2] == Path.home() / ".buvis"
        assert paths[3] == Path.cwd()

    def test_expanduser_tilde_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "~/custom")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        paths = ConfigurationLoader._get_search_paths()

        assert paths[0] == Path.home() / "custom"

    def test_legacy_buvis_always_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BUVIS_CONFIG_DIR", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        paths = ConfigurationLoader._get_search_paths()

        assert Path.home() / ".buvis" in paths

    def test_cwd_always_last(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUVIS_CONFIG_DIR", "/override")

        paths = ConfigurationLoader._get_search_paths()

        assert paths[-1] == Path.cwd()


class TestGetCandidateFiles:
    def test_empty_paths_returns_empty(self) -> None:
        result = ConfigurationLoader._get_candidate_files([], None)

        assert result == []

    def test_single_path_no_tool(self) -> None:
        result = ConfigurationLoader._get_candidate_files([Path("/cfg")], None)

        assert result == [Path("/cfg/buvis.yaml")]

    def test_multiple_paths_no_tool(self) -> None:
        paths = [Path("/a"), Path("/b")]

        result = ConfigurationLoader._get_candidate_files(paths, None)

        assert result == [Path("/a/buvis.yaml"), Path("/b/buvis.yaml")]

    def test_single_path_with_tool(self) -> None:
        result = ConfigurationLoader._get_candidate_files([Path("/cfg")], "payroll")

        assert result == [Path("/cfg/buvis.yaml"), Path("/cfg/buvis-payroll.yaml")]

    def test_multiple_paths_with_tool_maintains_interleaved_order(self) -> None:
        paths = [Path("/a"), Path("/b")]

        result = ConfigurationLoader._get_candidate_files(paths, "myapp")

        expected = [
            Path("/a/buvis.yaml"),
            Path("/a/buvis-myapp.yaml"),
            Path("/b/buvis.yaml"),
            Path("/b/buvis-myapp.yaml"),
        ]
        assert result == expected

    def test_empty_string_tool_name_treated_as_no_tool(self) -> None:
        result = ConfigurationLoader._get_candidate_files([Path("/cfg")], "")

        assert result == [Path("/cfg/buvis.yaml")]


class TestMergeConfigs:
    """Tests for merge_configs deep merge functionality."""

    def test_merge_single_dict(self) -> None:
        """Single dict returns copy."""
        result = ConfigurationLoader.merge_configs({"a": 1})

        assert result == {"a": 1}

    def test_merge_two_simple_dicts(self) -> None:
        """Two dicts merge keys."""
        result = ConfigurationLoader.merge_configs({"a": 1}, {"b": 2})

        assert result == {"a": 1, "b": 2}

    def test_merge_empty_dict(self) -> None:
        """Empty dict merges with no effect."""
        result = ConfigurationLoader.merge_configs({}, {"a": 1})

        assert result == {"a": 1}

    def test_merge_no_args(self) -> None:
        """No args returns empty dict."""
        result = ConfigurationLoader.merge_configs()

        assert result == {}

    def test_nested_merge(self) -> None:
        """Nested dicts merge recursively."""
        base = {"db": {"host": "localhost", "port": 5432}}
        override = {"db": {"port": 3306}}

        result = ConfigurationLoader.merge_configs(base, override)

        assert result == {"db": {"host": "localhost", "port": 3306}}

    def test_deeply_nested_merge(self) -> None:
        """Deeply nested dicts merge correctly."""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"c": 99}}}

        result = ConfigurationLoader.merge_configs(base, override)

        assert result == {"a": {"b": {"c": 99, "d": 2}}}

    def test_three_way_nested_merge(self) -> None:
        """Three configs merge in order."""
        a = {"x": {"y": 1}}
        b = {"x": {"z": 2}}
        c = {"x": {"y": 3}}

        result = ConfigurationLoader.merge_configs(a, b, c)

        assert result == {"x": {"y": 3, "z": 2}}

    def test_non_dict_replaces_dict(self) -> None:
        """Non-dict value replaces dict."""
        base = {"key": {"nested": "value"}}
        override = {"key": "string"}

        result = ConfigurationLoader.merge_configs(base, override)

        assert result == {"key": "string"}

    def test_dict_replaces_non_dict(self) -> None:
        """Dict replaces non-dict value."""
        base = {"key": "string"}
        override = {"key": {"nested": "value"}}

        result = ConfigurationLoader.merge_configs(base, override)

        assert result == {"key": {"nested": "value"}}

    def test_list_replaces_list(self) -> None:
        """Lists are replaced, not merged."""
        base = {"items": [1, 2]}
        override = {"items": [3, 4, 5]}

        result = ConfigurationLoader.merge_configs(base, override)

        assert result == {"items": [3, 4, 5]}

    def test_none_replaces_value(self) -> None:
        """None replaces existing value."""
        base = {"key": "value"}
        override = {"key": None}

        result = ConfigurationLoader.merge_configs(base, override)

        assert result == {"key": None}


class TestMissingEnvVarError:
    """Tests for MissingEnvVarError exception."""

    def test_stores_var_names(self) -> None:
        """Exception stores var_names attribute."""
        err = MissingEnvVarError(["FOO", "BAR"])

        assert err.var_names == ["FOO", "BAR"]

    def test_message_format_single(self) -> None:
        """Message formatted correctly for single var."""
        err = MissingEnvVarError(["DB_PASSWORD"])

        assert str(err) == "Missing required env vars: DB_PASSWORD"

    def test_message_format_multiple(self) -> None:
        """Message formatted correctly for multiple vars."""
        err = MissingEnvVarError(["FOO", "BAR", "BAZ"])

        assert str(err) == "Missing required env vars: FOO, BAR, BAZ"

    def test_catchable_by_type(self) -> None:
        """Exception can be caught by type."""
        with pytest.raises(MissingEnvVarError) as exc_info:
            raise MissingEnvVarError(["SECRET"])

        assert exc_info.value.var_names == ["SECRET"]

    def test_is_exception_subclass(self) -> None:
        """MissingEnvVarError is Exception subclass."""
        assert issubclass(MissingEnvVarError, Exception)


class TestIsWorldWritable:
    """Tests for _is_world_writable error handling."""

    def test_oserror_returns_false(self, tmp_path: Path) -> None:
        """Lines 141-142: OSError in _is_world_writable returns False."""
        from unittest.mock import MagicMock

        mock_path = MagicMock(spec=Path)
        mock_path.stat.side_effect = OSError("Permission denied")

        result = ConfigurationLoader._is_world_writable(mock_path)
        assert result is False


class TestFindConfigFilesLogging:
    """Tests for find_config_files logging behavior."""

    def test_unsafe_path_logged_and_skipped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Unsafe symlink path is logged as warning and skipped."""
        import logging
        from unittest.mock import patch

        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        config_file = tmp_path / "buvis.yaml"
        config_file.write_text("key: value")

        with patch.object(
            ConfigurationLoader,
            "_is_safe_path",
            return_value=False,
        ):
            with caplog.at_level(logging.WARNING):
                result = ConfigurationLoader.find_config_files()

            assert result == []
            assert "unsafe" in caplog.text.lower()

    def test_permission_denied_logged_debug(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Permission error is logged at debug level."""
        import logging

        monkeypatch.setenv("BUVIS_CONFIG_DIR", str(tmp_path))
        config = tmp_path / "buvis.yaml"
        config.write_text("key: value")

        original_is_file = Path.is_file

        def mock_is_file(self):
            if self == config:
                raise PermissionError("Access denied")
            return original_is_file(self)

        monkeypatch.setattr(Path, "is_file", mock_is_file)

        with caplog.at_level(logging.DEBUG):
            result = ConfigurationLoader.find_config_files()

        assert result == []
        assert "Permission denied" in caplog.text

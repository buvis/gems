from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from buvis.pybase.result import FatalError

from backup.config import BackupConfig, BackupInstance, applicable_instances, load_config


def _write(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text), encoding="utf-8")


class TestBackupInstanceModel:
    def test_use_instance_validates(self) -> None:
        inst = BackupInstance.model_validate({"use": "tar-archive", "with": {"source": "/a", "out": "/b"}})
        assert inst.use == "tar-archive"
        assert inst.with_ == {"source": "/a", "out": "/b"}
        assert inst.enabled is True

    def test_unknown_key_raises(self) -> None:
        with pytest.raises(ValueError, match="bogus"):
            BackupInstance.model_validate({"use": "tar-archive", "bogus": 1})

    def test_tags_and_order(self) -> None:
        inst = BackupInstance.model_validate({"use": "tar-archive", "order": 5, "tags": ["nightly"]})
        assert inst.order == 5
        assert inst.tags == ("nightly",)


class TestBackupConfigModel:
    def test_unknown_top_level_key_raises(self) -> None:
        with pytest.raises(ValueError, match="nonsense"):
            BackupConfig.model_validate({"nonsense": True})


class TestLoadConfigDefault:
    def test_no_user_config_returns_bundled_default(self, mocker) -> None:
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert "git-src" in cfg.instances
        assert cfg.instances["git-src"].use == "tar-archive"
        # a representative slice of the ~35 defaults ships
        assert "node_modules" in cfg.excludes
        assert "target" in cfg.excludes
        assert "__pycache__" in cfg.excludes
        assert ".DS_Store" in cfg.excludes

    def test_default_exclude_count_matches_script(self, mocker) -> None:
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        # the wrapped backup-git script ships exactly 32 --exclude patterns
        assert len(cfg.excludes) == 32

    def test_default_source_expands_home_not_literal(self, mocker, tmp_path: Path) -> None:
        """FIX A: the bundled default.yaml's ``${HOME}/git/src`` must be loaded
        through the env-substituting loader so it expands to the real home dir,
        not left as a literal ``${HOME}`` (which would be an unusable source)."""
        home = tmp_path / "home"
        home.mkdir()
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        mocker.patch.dict("os.environ", {"HOME": str(home)}, clear=False)
        cfg = load_config()
        source = cfg.instances["git-src"].with_["source"]
        assert isinstance(source, str)
        assert "${HOME}" not in source
        assert source == f"{home}/git/src"
        out = cfg.instances["git-src"].with_["out"]
        assert isinstance(out, str)
        assert "${HOME}" not in out
        assert out.startswith(f"{home}/.local/backup/")

    def test_home_unset_raises_fatal_not_missing_env_var(self, mocker) -> None:
        """FIX F: with HOME unset, default.yaml's ``${HOME}`` becomes a missing
        required var; load_config must translate it to FatalError (the CLI
        catches only that), never leak a raw MissingEnvVarError."""
        from buvis.pybase.configuration import MissingEnvVarError

        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        mocker.patch.dict("os.environ", {}, clear=True)
        with pytest.raises(FatalError) as exc_info:
            load_config()
        assert not isinstance(exc_info.value, MissingEnvVarError)
        assert "bundled default configuration" in str(exc_info.value)


class TestExcludeLayering:
    def test_excludes_plus_adds_without_relisting(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-backup.yaml"
        _write(user, "excludes+: [scratch-notes]\n")
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert "scratch-notes" in cfg.excludes
        assert "node_modules" in cfg.excludes  # defaults survive

    def test_excludes_minus_removes_a_default(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-backup.yaml"
        _write(user, "excludes-: [target]\n")
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert "target" not in cfg.excludes
        assert "dist" in cfg.excludes  # others survive

    def test_layered_add_then_machine_remove(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "user.yaml"
        machine = tmp_path / "machine.yaml"
        _write(user, "excludes+: [scratch, target-notes]\n")
        _write(machine, "excludes-: [target]\n")
        # find_config_files_ranked returns low-to-high; machine wins last.
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user, machine])
        cfg = load_config()
        assert "scratch" in cfg.excludes
        assert "target-notes" in cfg.excludes
        assert "target" not in cfg.excludes


class TestLoadConfigValidation:
    def test_unknown_capability_raises_fatal(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-backup.yaml"
        _write(user, "instances:\n  x:\n    use: no-such\n")
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="unknown capability 'no-such'"):
            load_config()

    def test_unknown_with_input_raises_fatal(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-backup.yaml"
        _write(user, "instances:\n  x:\n    use: tar-archive\n    with:\n      bogus: 1\n")
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="unknown input"):
            load_config()

    def test_known_with_input_accepted(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-backup.yaml"
        _write(user, "instances:\n  x:\n    use: tar-archive\n    with:\n      source: /a\n      out: /b\n")
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert cfg.instances["x"].with_ == {"source": "/a", "out": "/b"}

    def test_invalid_schema_raises_fatal(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-backup.yaml"
        _write(user, "instances: not-a-map\n")
        mocker.patch("backup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="invalid backup configuration"):
            load_config()

    def test_malformed_yaml_raises_fatal_not_yamlerror(self, tmp_path: Path) -> None:
        """Finding 6: a syntactically broken YAML config file is translated to
        FatalError (the CLI catches only that), never a raw yaml.YAMLError."""
        import yaml

        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        # unterminated flow mapping -> yaml.safe_load raises yaml.YAMLError
        _write(cfg_dir / "buvis-backup.yaml", "instances: {oops: \n  broken: [1, 2\n")
        with pytest.raises(FatalError) as exc_info:
            load_config(config_dir=str(cfg_dir))
        assert not isinstance(exc_info.value, yaml.YAMLError)
        assert str(cfg_dir / "buvis-backup.yaml") in str(exc_info.value)


class TestApplicableInstances:
    def test_sorted_by_order_then_name(self) -> None:
        cfg = BackupConfig.model_validate(
            {
                "instances": {
                    "b": {"use": "tar-archive", "order": 10},
                    "a": {"use": "tar-archive", "order": 10},
                    "c": {"use": "tar-archive", "order": 5},
                },
            },
        )
        names = [name for name, _ in applicable_instances(cfg)]
        assert names == ["c", "a", "b"]

    def test_disabled_excluded(self) -> None:
        cfg = BackupConfig.model_validate(
            {"instances": {"x": {"use": "tar-archive", "enabled": False}}},
        )
        assert applicable_instances(cfg) == []

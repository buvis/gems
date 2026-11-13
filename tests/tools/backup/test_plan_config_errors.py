from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from buvis.pybase.result import FatalError

from backup.config import load_config


def _write(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text), encoding="utf-8")


class TestSharedFilesTolerateForeignKeys:
    def test_shared_config_debug_key_keeps_bundled_instances(self, tmp_path: Path) -> None:
        _write(tmp_path / "config.yaml", "debug: true\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "git-src" in cfg.instances
        assert "node_modules" in cfg.excludes

    def test_shared_config_other_tool_section_is_ignored(self, tmp_path: Path) -> None:
        _write(tmp_path / "config.yaml", "bim:\n  vault: /somewhere\n  nested:\n    a: 1\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "git-src" in cfg.instances
        assert not hasattr(cfg, "bim")

    def test_shared_buvis_yaml_other_tool_section_is_ignored(self, tmp_path: Path) -> None:
        _write(tmp_path / "buvis.yaml", "sysup:\n  steps: []\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "git-src" in cfg.instances


class TestGlobalKeysInBackupFile:
    def test_debug_and_log_level_in_backup_file_are_accepted(self, tmp_path: Path) -> None:
        _write(tmp_path / "buvis-backup.yaml", "debug: true\nlog_level: DEBUG\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "git-src" in cfg.instances

    def test_global_keys_do_not_hide_backup_specific_directive(self, tmp_path: Path) -> None:
        _write(tmp_path / "buvis-backup.yaml", "debug: true\nexcludes+: [scratch-notes]\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "scratch-notes" in cfg.excludes
        assert "node_modules" in cfg.excludes


class TestPlanErrorsNameTheFile:
    def test_typo_key_names_file_and_key(self, tmp_path: Path) -> None:
        backup_file = tmp_path / "buvis-backup.yaml"
        _write(backup_file, "instnaces:\n  x: {use: tar-archive}\n")
        with pytest.raises(FatalError) as exc_info:
            load_config(config_dir=str(tmp_path))
        message = str(exc_info.value)
        assert str(backup_file) in message
        assert "instnaces" in message

    def test_type_error_names_file_and_field_without_pydantic_dump(self, tmp_path: Path) -> None:
        backup_file = tmp_path / "buvis-backup.yaml"
        _write(backup_file, "excludes: 5\n")
        with pytest.raises(FatalError) as exc_info:
            load_config(config_dir=str(tmp_path))
        message = str(exc_info.value)
        assert str(backup_file) in message
        assert "excludes" in message
        assert "errors.pydantic.dev" not in message
        assert "For further information visit" not in message
        assert "\n" not in message.strip()

    def test_bad_instance_in_shared_file_is_blamed_on_shared_file(self, tmp_path: Path) -> None:
        shared = tmp_path / "config.yaml"
        backup_file = tmp_path / "buvis-backup.yaml"
        _write(shared, "instances:\n  broken:\n    use: tar-archive\n    bogus: 1\n")
        _write(backup_file, "instances:\n  good:\n    use: tar-archive\n    with:\n      source: /a\n      out: /b\n")
        with pytest.raises(FatalError) as exc_info:
            load_config(config_dir=str(tmp_path))
        message = str(exc_info.value)
        assert str(shared) in message
        assert str(backup_file) not in message

    def test_bad_instance_in_backup_file_is_blamed_on_backup_file(self, tmp_path: Path) -> None:
        shared = tmp_path / "config.yaml"
        backup_file = tmp_path / "buvis-backup.yaml"
        _write(shared, "instances:\n  good:\n    use: tar-archive\n    with:\n      source: /a\n      out: /b\n")
        _write(backup_file, "instances:\n  broken:\n    use: tar-archive\n    bogus: 1\n")
        with pytest.raises(FatalError) as exc_info:
            load_config(config_dir=str(tmp_path))
        message = str(exc_info.value)
        assert str(backup_file) in message
        assert str(shared) not in message

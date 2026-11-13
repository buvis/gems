from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest
from buvis.pybase.result import FatalError
from click.testing import CliRunner

from sysup.cli import cli
from sysup.config import load_config

if TYPE_CHECKING:
    from pathlib import Path

_PYDANTIC_NOISE = ("errors.pydantic.dev", "For further information visit")


def _write(path: Path, text: str) -> Path:
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def wide_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "500")


def _run_list(config_dir: Path):
    return CliRunner().invoke(cli, ["--config-dir", str(config_dir), "--list"])


class TestSharedFilesTolerateForeignKeys:
    def test_debug_in_shared_config_yaml_loads(self, tmp_path: Path) -> None:
        _write(tmp_path / "config.yaml", "debug: true\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "brew" in cfg.commands

    def test_other_tool_section_in_shared_config_yaml_loads(self, tmp_path: Path) -> None:
        _write(tmp_path / "config.yaml", "bim:\n  path_zettelkasten: /tmp/x\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "brew" in cfg.commands

    def test_global_keys_in_buvis_yaml_load(self, tmp_path: Path) -> None:
        _write(tmp_path / "buvis.yaml", "debug: true\nlog_level: DEBUG\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "brew" in cfg.commands

    def test_list_exits_zero_with_foreign_keys_in_config_yaml(self, tmp_path: Path) -> None:
        _write(tmp_path / "config.yaml", "debug: true\nbim:\n  path_zettelkasten: /tmp/x\n")
        result = _run_list(tmp_path)
        assert result.exit_code == 0, result.output
        assert "brew" in result.output
        assert "Extra inputs" not in result.output

    def test_list_exits_zero_with_global_keys_in_buvis_yaml(self, tmp_path: Path) -> None:
        _write(tmp_path / "buvis.yaml", "debug: true\nlog_level: DEBUG\n")
        result = _run_list(tmp_path)
        assert result.exit_code == 0, result.output

    def test_shared_plan_keys_still_apply_next_to_foreign_keys(self, tmp_path: Path) -> None:
        _write(tmp_path / "config.yaml", "debug: true\ncommands:\n  brew:\n    order: 777\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert cfg.commands["brew"].order == 777


class TestSysupSpecificFile:
    def test_global_settings_keys_in_buvis_sysup_yaml_load(self, tmp_path: Path) -> None:
        _write(tmp_path / "buvis-sysup.yaml", "debug: true\nlog_level: DEBUG\n")
        cfg = load_config(config_dir=str(tmp_path))
        assert "brew" in cfg.commands

    def test_typo_top_level_key_names_file_and_key(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "buvis-sysup.yaml", "comands:\n  x:\n    steps: [[x]]\n")
        with pytest.raises(FatalError) as excinfo:
            load_config(config_dir=str(tmp_path))
        assert str(path) in str(excinfo.value)
        assert "comands" in str(excinfo.value)

    def test_valid_commands_entry_still_listed(self, tmp_path: Path) -> None:
        _write(
            tmp_path / "buvis-sysup.yaml",
            "commands:\n  zz-custom-tool:\n    order: 15\n    steps: [[custom, update]]\n",
        )
        result = _run_list(tmp_path)
        assert result.exit_code == 0, result.output
        assert "zz-custom-tool" in result.output


class TestMergeDirectiveOnMapping:
    def test_list_directive_on_mapping_key_raises_fatal_naming_file(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "buvis-sysup.yaml", "commands-: [x]\n")
        with pytest.raises(FatalError) as excinfo:
            load_config(config_dir=str(tmp_path))
        assert type(excinfo.value) is FatalError
        assert str(path) in str(excinfo.value)

    def test_list_directive_on_mapping_key_prints_clean_line_through_cli(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "buvis-sysup.yaml", "commands-: [x]\n")
        result = _run_list(tmp_path)
        assert result.exit_code == 1
        assert " ✘ " in result.output
        assert str(path) in result.output
        assert "Traceback" not in result.output


class TestTypeErrors:
    def test_prime_type_error_names_file_and_field_without_pydantic_url(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "buvis-sysup.yaml", "prime: 5\n")
        with pytest.raises(FatalError) as excinfo:
            load_config(config_dir=str(tmp_path))
        message = str(excinfo.value)
        assert str(path) in message
        assert "prime" in message
        for noise in _PYDANTIC_NOISE:
            assert noise not in message

    def test_prime_type_error_is_one_console_line(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "buvis-sysup.yaml", "prime: 5\n")
        result = _run_list(tmp_path)
        assert result.exit_code == 1
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert len(lines) == 1, result.output
        assert " ✘ " in lines[0]
        assert str(path) in lines[0]
        assert "prime" in lines[0]
        for noise in _PYDANTIC_NOISE:
            assert noise not in result.output

    def test_bad_mapping_entry_is_blamed_on_the_file_that_supplied_it(self, tmp_path: Path) -> None:
        bad = _write(tmp_path / "config.yaml", "commands:\n  bad:\n    order: notanint\n    steps: [[x]]\n")
        good = _write(tmp_path / "buvis-sysup.yaml", "commands:\n  good:\n    steps: [[y]]\n")
        with pytest.raises(FatalError) as excinfo:
            load_config(config_dir=str(tmp_path))
        assert str(bad) in str(excinfo.value)
        assert str(good) not in str(excinfo.value)

    def test_field_name_in_message_follows_the_offending_field(self, tmp_path: Path) -> None:
        _write(tmp_path / "buvis-sysup.yaml", "ntfy: 5\n")
        with pytest.raises(FatalError) as excinfo:
            load_config(config_dir=str(tmp_path))
        assert "ntfy" in str(excinfo.value)
        assert "prime" not in str(excinfo.value)

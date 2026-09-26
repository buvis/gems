from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from buvis.pybase.result import FatalError

from sysup.config import SysupCommand, SysupConfig, load_config


class TestSysupCommandModel:
    def test_run_entry_validates(self) -> None:
        cmd = SysupCommand.model_validate({"steps": [["brew", "update"]]})
        assert cmd.steps == (("brew", "update"),)
        assert cmd.use is None
        assert cmd.enabled is True
        assert cmd.order == 100

    def test_use_entry_validates(self) -> None:
        cmd = SysupCommand.model_validate({"use": "pip-outdated"})
        assert cmd.use == "pip-outdated"
        assert cmd.steps is None

    def test_with_alias_populates_under_extra_forbid(self) -> None:
        cmd = SysupCommand.model_validate({"use": "nvim-mason", "with": {"timeout": 300}})
        assert cmd.with_ == {"timeout": 300}

    def test_both_steps_and_use_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one of"):
            SysupCommand.model_validate({"steps": [["brew"]], "use": "pip-outdated"})

    def test_neither_steps_nor_use_raises(self) -> None:
        with pytest.raises(ValueError, match="exactly one of"):
            SysupCommand.model_validate({"order": 10})

    def test_unknown_entry_key_raises(self) -> None:
        with pytest.raises(ValueError, match="bogus"):
            SysupCommand.model_validate({"use": "pip-outdated", "bogus": 1})

    def test_full_envelope(self) -> None:
        cmd = SysupCommand.model_validate(
            {
                "order": 5,
                "enabled": False,
                "when": {"os": "darwin", "check": "brew"},
                "interactive": True,
                "timeout": 30,
                "continue_on_error": True,
                "tags": ["a", "b"],
                "steps": [["brew", "update"]],
            },
        )
        assert cmd.enabled is False
        assert cmd.when.os == "darwin"
        assert cmd.when.check == "brew"
        assert cmd.interactive is True
        assert cmd.timeout == 30
        assert cmd.continue_on_error is True
        assert cmd.tags == ("a", "b")


class TestSysupConfigModel:
    def test_unknown_top_level_key_raises(self) -> None:
        with pytest.raises(ValueError, match="nonsense"):
            SysupConfig.model_validate({"nonsense": True})

    def test_when_unknown_os_raises(self) -> None:
        with pytest.raises(ValueError):
            SysupConfig.model_validate({"commands": {"x": {"when": {"os": "plan9"}, "steps": [["x"]]}}})


def _write(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text), encoding="utf-8")


class TestLoadConfig:
    def test_no_user_config_returns_bundled_default(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert "brew" in cfg.commands
        assert "apt" in cfg.commands
        assert cfg.prime == ("sudo-prime",)

    def test_user_layer_adds_and_overrides_by_key(self, mocker, tmp_path: Path) -> None:
        """Keyed-map deep-merge: a user layer adds one key and overrides one field
        of another, and every bundled key survives (regression guard for the
        no-list decision)."""
        user = tmp_path / "buvis-sysup.yaml"
        _write(
            user,
            """
            commands:
              brew:
                order: 999
              custom-tool:
                order: 15
                steps:
                  - [custom, update]
            """,
        )
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert cfg.commands["brew"].order == 999
        assert cfg.commands["brew"].steps == (("brew", "update"), ("brew", "upgrade"), ("brew", "cleanup"))
        assert "custom-tool" in cfg.commands
        assert "mise" in cfg.commands  # bundled key survives

    def test_empty_commands_does_not_wipe_default(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "commands: {}\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert "brew" in cfg.commands

    def test_higher_priority_layer_wins(self, mocker, tmp_path: Path) -> None:
        low = tmp_path / "low.yaml"
        high = tmp_path / "high.yaml"
        _write(low, "commands:\n  brew:\n    order: 100\n")
        _write(high, "commands:\n  brew:\n    order: 200\n")
        # find_config_files_ranked returns low-to-high; last wins.
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[low, high])
        cfg = load_config()
        assert cfg.commands["brew"].order == 200

    def test_disable_via_enabled_false(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "commands:\n  helm:\n    enabled: false\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert cfg.commands["helm"].enabled is False

    def test_unknown_capability_raises_fatal(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "commands:\n  x:\n    use: no-such-capability\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="unknown capability 'no-such-capability'"):
            load_config()

    def test_unknown_with_input_raises_fatal(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "commands:\n  x:\n    use: helm-repo-update\n    with:\n      bogus: 1\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="unknown input"):
            load_config()

    def test_known_with_input_accepted(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "commands:\n  nvim:\n    use: nvim-mason\n    with:\n      timeout: 300\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert cfg.commands["nvim"].with_ == {"timeout": 300}

    def test_unknown_prime_capability_raises_fatal(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "prime:\n  - not-a-capability\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="prime: unknown capability"):
            load_config()

    def test_invalid_schema_raises_fatal(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "commands:\n  x:\n    steps: not-a-list\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="invalid sysup configuration"):
            load_config()

    def test_env_substitution_and_literal(self, mocker, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("SYSUP_TEST_TOOL", "mytool")
        user = tmp_path / "buvis-sysup.yaml"
        _write(
            user,
            """
            commands:
              subst:
                order: 5
                steps:
                  - ["${SYSUP_TEST_TOOL}", "run"]
              literal:
                order: 6
                steps:
                  - ["echo", "$${NOT_EXPANDED}"]
            """,
        )
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert cfg.commands["subst"].steps == (("mytool", "run"),)
        assert cfg.commands["literal"].steps == (("echo", "${NOT_EXPANDED}"),)


class TestLoadConfigPriorityOrdering:
    """Regression guard for design Finding 1: a blind reversed() of
    find_config_files inverts precedence. load_config must feed
    find_config_files_ranked (low-to-high) straight to merge_configs so the
    highest-priority layer wins."""

    def test_ranked_order_last_wins(self, mocker, tmp_path: Path) -> None:
        cwd_file = tmp_path / "cwd.yaml"
        home_file = tmp_path / "home.yaml"
        env_file = tmp_path / "env.yaml"
        # Emulate find_config_files_ranked's contract: low-to-high priority.
        # cwd (lowest) < ~/.config/buvis < $BUVIS_CONFIG_DIR (highest).
        _write(cwd_file, "commands:\n  brew:\n    order: 1\n")
        _write(home_file, "commands:\n  brew:\n    order: 2\n")
        _write(env_file, "commands:\n  brew:\n    order: 3\n")
        mocker.patch(
            "sysup.config.ConfigurationLoader.find_config_files_ranked",
            return_value=[cwd_file, home_file, env_file],
        )
        cfg = load_config()
        assert cfg.commands["brew"].order == 3

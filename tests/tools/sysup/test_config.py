from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from buvis.pybase.result import FatalError

from sysup.config import ExpiryItem, NtfySpec, RefreshSpec, SysupCommand, SysupConfig, load_config


class TestSysupCommandModel:
    def test_run_entry_validates(self) -> None:
        cmd = SysupCommand.model_validate({"steps": [["brew", "update"]]})
        assert cmd.steps[0].argv == ("brew", "update")
        assert cmd.use is None
        assert cmd.enabled is True
        assert cmd.order == 100

    def test_sudo_defaults_false(self) -> None:
        cmd = SysupCommand.model_validate({"steps": [["brew", "update"]]})
        assert cmd.sudo is False

    def test_sudo_true_accepted(self) -> None:
        cmd = SysupCommand.model_validate({"steps": [["brew", "update"]], "sudo": True})
        assert cmd.sudo is True

    def test_legacy_config_without_sudo_key_still_validates(self) -> None:
        """A config predating the `sudo` field must keep loading unchanged."""
        cmd = SysupCommand.model_validate({"order": 10, "enabled": True, "steps": [["brew", "update"]]})
        assert cmd.sudo is False

    def test_step_object_carries_env_and_bare_list_is_sugar(self) -> None:
        cmd = SysupCommand.model_validate(
            {"steps": [["brew", "update"], {"argv": ["brew", "upgrade"], "env": {"HOMEBREW_NO_AUTO_UPDATE": "1"}}]}
        )
        assert cmd.steps[0].argv == ("brew", "update")
        assert cmd.steps[0].env == {}
        assert cmd.steps[1].argv == ("brew", "upgrade")
        assert cmd.steps[1].env == {"HOMEBREW_NO_AUTO_UPDATE": "1"}

    def test_string_step_is_a_bash_script_and_label_is_the_line_as_written(self) -> None:
        line = "VAR=1 brew upgrade --quiet | tee log"
        cmd = SysupCommand.model_validate({"steps": [line, ["brew", "cleanup"]]})
        assert cmd.steps[0].argv == ("bash", "-ec", line)
        assert cmd.steps[0].label == line
        assert cmd.steps[1].argv == ("brew", "cleanup")
        assert cmd.steps[1].label == "brew cleanup"

    def test_step_object_argv_may_be_a_shell_line(self) -> None:
        cmd = SysupCommand.model_validate({"steps": [{"argv": "brew doctor", "env": {"HOMEBREW_NO_AUTO_UPDATE": "1"}}]})
        assert cmd.steps[0].argv == ("bash", "-ec", "brew doctor")
        assert cmd.steps[0].env == {"HOMEBREW_NO_AUTO_UPDATE": "1"}

    @pytest.mark.parametrize("empty", [[], "", "  "])
    def test_empty_step_is_rejected_at_load(self, empty: object) -> None:
        with pytest.raises(ValueError, match="empty|at least 1"):
            SysupCommand.model_validate({"steps": [empty]})

    def test_step_cannot_take_refresh_only_stdin(self) -> None:
        """A pasted secret is a refresh concern; an ordinary step has no prompt."""
        with pytest.raises(ValueError, match="stdin"):
            SysupCommand.model_validate({"steps": [{"argv": ["gh", "auth"], "stdin": "secret"}]})

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
    def test_ntfy_section_validates_and_defaults(self) -> None:
        assert SysupConfig().ntfy == NtfySpec(url=None, topic=None, credentials_file=None)
        cfg = SysupConfig.model_validate(
            {"ntfy": {"url": "https://ntfy.example", "topic": "sysup", "credentials_file": "~/.ntfy"}}
        )
        assert cfg.ntfy.url == "https://ntfy.example"
        assert cfg.ntfy.topic == "sysup"
        assert cfg.ntfy.credentials_file == "~/.ntfy"
        with pytest.raises(ValueError, match="frozen"):
            cfg.ntfy.topic = "other"

    def test_ntfy_unknown_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="bogus"):
            SysupConfig.model_validate({"ntfy": {"bogus": "value"}})

    def test_unknown_top_level_key_raises(self) -> None:
        with pytest.raises(ValueError, match="nonsense"):
            SysupConfig.model_validate({"nonsense": True})

    def test_when_unknown_os_raises(self) -> None:
        with pytest.raises(ValueError):
            SysupConfig.model_validate({"commands": {"x": {"when": {"os": "plan9"}, "steps": [["x"]]}}})


def _write(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text), encoding="utf-8")


class TestLoadConfig:
    def test_ntfy_local_layer_merges_over_shared_config(self, mocker, tmp_path: Path) -> None:
        shared = tmp_path / "buvis-sysup.yaml"
        local = tmp_path / "buvis-sysup.local.yaml"
        _write(shared, "ntfy:\n  url: https://ntfy.example\n  topic: shared\n")
        _write(local, "ntfy:\n  topic: local\n  credentials_file: ~/.ntfy\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[shared, local])
        cfg = load_config()
        assert cfg.ntfy == NtfySpec(url="https://ntfy.example", topic="local", credentials_file="~/.ntfy")

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
        assert [s.label for s in cfg.commands["brew"].steps] == [
            "brew update",
            "HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS=1 brew upgrade --quiet",
            "brew cleanup",
        ]
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
              shell:
                order: 7
                steps:
                  - echo "${SYSUP_TEST_TOOL}" $${LATER}
            """,
        )
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert cfg.commands["subst"].steps[0].argv == ("mytool", "run")
        assert cfg.commands["literal"].steps[0].argv == ("echo", "${NOT_EXPANDED}")
        # The loader expands first; `$${...}` is how a `${...}` reaches bash.
        assert cfg.commands["shell"].steps[0].label == 'echo "mytool" ${LATER}'


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


class TestExpiryRegistry:
    def test_expiry_item_validates_with_defaults(self) -> None:
        item = ExpiryItem.model_validate({"use": "x509-expiry", "with": {"path": "/c.pem"}})
        assert item.use == "x509-expiry"
        assert item.with_ == {"path": "/c.pem"}
        assert item.warn_days == 30
        assert item.enabled is True
        assert item.refresh is None

    def test_enabled_gh_item_without_probe_is_rejected(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(
            user,
            """
            expiry:
              gh-agent:
                use: gh-token-expiry
                with:
                  config_dir: ~/.config/gh-agent
                enabled: true
            """,
        )
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="requires input 'probe'"):
            load_config()

    def test_disabled_template_without_probe_loads(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(
            user,
            """
            expiry:
              gh-agent:
                use: gh-token-expiry
                with:
                  config_dir: ~/.config/gh-agent
                enabled: false
            """,
        )
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        cfg = load_config()
        assert cfg.expiry["gh-agent"].enabled is False

    def test_refresh_commands_take_the_same_shapes_as_steps(self) -> None:
        commands = ["gh auth status", {"argv": "gh auth login --with-token", "stdin": "secret"}]
        spec = RefreshSpec.model_validate({"instructions": "x", "commands": commands})
        assert spec.commands[0].argv == ("bash", "-ec", "gh auth status")
        assert spec.commands[1].label == "gh auth login --with-token"
        assert spec.commands[1].stdin == "secret"

    def test_unknown_expiry_capability_rejected(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "expiry:\n  x:\n    use: no-such-expiry\n    enabled: false\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="unknown expiry capability 'no-such-expiry'"):
            load_config()

    def test_needs_unknown_item_rejected(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(user, "commands:\n  brew:\n    steps: [[brew, update]]\n    needs: [ghost]\n")
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="needs unknown expiry item 'ghost'"):
            load_config()

    def test_item_and_command_name_collision_rejected(self, mocker, tmp_path: Path) -> None:
        user = tmp_path / "buvis-sysup.yaml"
        _write(
            user,
            """
            commands:
              shared:
                steps: [[tool]]
            expiry:
              shared:
                use: x509-expiry
                with: { path: /c.pem }
            """,
        )
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[user])
        with pytest.raises(FatalError, match="'shared' is both a command and an expiry item"):
            load_config()

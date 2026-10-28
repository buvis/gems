from __future__ import annotations

from sysup.config import applicable_commands, load_config


def _plan_names(platform: str, mocker) -> list[str]:
    mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
    mocker.patch("sysup.config.sys.platform", platform)
    # Every candidate binary resolves, so the plan is the full host set.
    mocker.patch("sysup.config.shutil.which", side_effect=lambda name: "/usr/local/bin/" + name)
    cfg = load_config()
    return [name for name, _ in applicable_commands(cfg)]


class TestDefaultConfigEquivalence:
    def test_darwin_plan_matches_old_sysup_mac(self, mocker) -> None:
        """Zero-config darwin plan == today's `sysup mac` plus the former
        standalone `sysup nvim`: brew, npm-check, pip (python-packages),
        uv-tool-python, uv,
        helm, mise — mise last among the tool managers — then pipx-python
        (needs mise's new global python), then nvim (mason)."""
        names = _plan_names("darwin", mocker)
        assert names == [
            "brew",
            "npm-check",
            "python-packages",
            "uv-tool-python",
            "uv",
            "helm",
            "mise",
            "pipx-python",
            "nvim",
        ]
        assert names.index("mise") < names.index("pipx-python") < names.index("nvim")

    def test_linux_plan_matches_old_sysup_wsl(self, mocker) -> None:
        """Zero-config linux plan == today's `sysup wsl` (apt then snap) plus the
        former standalone `sysup nvim`, which had no platform guard."""
        names = _plan_names("linux", mocker)
        assert names == ["apt", "snap", "nvim"]

    def test_nvim_is_a_cross_platform_mason_capability(self, mocker) -> None:
        """The former standalone `sysup nvim` is restored as a `use: nvim-mason`
        entry with no `os` guard (only `check: nvim`), so it applies on any host
        where nvim resolves — matching the old subcommand's behaviour."""
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        nvim = cfg.commands["nvim"]
        assert nvim.use == "nvim-mason"
        assert nvim.when.os is None
        assert nvim.when.check == "nvim"

    def test_darwin_does_not_include_linux_entries(self, mocker) -> None:
        names = _plan_names("darwin", mocker)
        assert "apt" not in names
        assert "snap" not in names

    def test_linux_does_not_include_darwin_entries(self, mocker) -> None:
        names = _plan_names("linux", mocker)
        for mac_entry in ("brew", "npm-check", "python-packages", "uv-tool-python", "uv", "helm", "mise"):
            assert mac_entry not in names

    def test_uv_tool_python_runs_before_unchanged_uv_upgrades(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        entry = cfg.commands["uv-tool-python"]
        assert entry.order == 35
        assert entry.when.os == "darwin"
        assert entry.when.check == "uv"
        assert entry.use == "uv-tool-python"
        uv = cfg.commands["uv"]
        assert uv.order == 40
        assert [s.label for s in uv.steps] == ["uv python upgrade", "uv tool upgrade --all"]

    def test_pip_runs_between_npm_check_and_uv_on_darwin(self, mocker) -> None:
        """1.4: the former mac->pip in-code delegation is now an independent entry
        ordered between npm-check and uv."""
        names = _plan_names("darwin", mocker)
        assert names.index("npm-check") < names.index("python-packages") < names.index("uv")

    def test_default_primes_sudo(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.prime == ("sudo-prime",)

    def test_brew_is_a_run_entry_with_early_abort_sequence(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert [s.label for s in cfg.commands["brew"].steps] == [
            "brew update",
            "HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS=1 brew upgrade --quiet",
            "brew cleanup",
        ]

    def test_brew_upgrade_leaves_self_updating_casks_alone(self, mocker) -> None:
        """Casks that update themselves (browsers, editors) are skipped by
        `brew upgrade` through Homebrew's own switch, set as a shell prefix on
        that one step only."""
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        update, upgrade, cleanup = cfg.commands["brew"].steps
        assert upgrade.label.startswith("HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS=1 brew upgrade")
        assert "HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS" not in update.label + cleanup.label

    def test_bundled_steps_are_shell_lines(self, mocker) -> None:
        """The bundled default shows the preferred spelling: every step is one
        `bash -ec` line, never an argv array."""
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        for name, command in cfg.commands.items():
            for step in command.steps or ():
                assert step.argv[:2] == ("bash", "-ec"), name

    def test_mise_self_update_never_waits_for_a_prompt(self, mocker) -> None:
        """sysup captures mise's output, so a confirmation prompt can never be
        answered and the step fails with "self-update cancelled"."""
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.commands["mise"].steps[0].label == "mise self-update --yes"

    def test_npm_check_is_interactive(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.commands["npm-check"].interactive is True

    def test_brew_is_interactive_so_its_sudo_prompt_is_visible(self, mocker) -> None:
        """Homebrew resets the sudo ticket before its first sudo call, so a cask
        upgrade prompts for a password; captured mode hides that prompt behind
        the spinner and the run appears to hang."""
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.commands["brew"].interactive is True

    def test_apt_invokes_sudo_in_every_step(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert [s.label for s in cfg.commands["apt"].steps] == [
            "sudo apt update",
            "sudo apt upgrade -y",
            "sudo apt autoremove -y",
        ]

    def test_brew_has_sudo_flag_set(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.commands["brew"].sudo is True

    def test_apt_and_snap_do_not_set_sudo_flag(self, mocker) -> None:
        """apt/snap invoke sudo inside their steps, not via the flag — the flag stays default."""
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.commands["apt"].sudo is False
        assert cfg.commands["snap"].sudo is False


class TestDefaultExpiryTemplate:
    def test_gh_agent_template_is_disabled_and_has_no_probe(self, mocker) -> None:
        """The bundled gh-agent item ships disabled with no probe, so it adds no
        command and loads without the enabled-item required-input rule firing."""
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        item = cfg.expiry["gh-agent"]
        assert item.enabled is False
        assert item.use == "gh-token-expiry"
        assert item.with_ == {"config_dir": "~/.config/gh-agent"}
        assert "probe" not in item.with_
        assert item.refresh is not None
        assert item.refresh.commands[0].stdin == "secret"
        assert item.refresh.commands[0].label == "gh auth login --hostname github.com --with-token --insecure-storage"
        assert "gh-agent" not in cfg.commands

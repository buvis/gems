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
        """Zero-config darwin plan == today's `sysup mac`: brew, npm-check, pip
        (python-packages), uv, helm, mise — in that order, mise last."""
        names = _plan_names("darwin", mocker)
        assert names == ["brew", "npm-check", "python-packages", "uv", "helm", "mise"]
        assert names[-1] == "mise"

    def test_linux_plan_matches_old_sysup_wsl(self, mocker) -> None:
        """Zero-config linux plan == today's `sysup wsl`: apt then snap."""
        names = _plan_names("linux", mocker)
        assert names == ["apt", "snap"]

    def test_darwin_does_not_include_linux_entries(self, mocker) -> None:
        names = _plan_names("darwin", mocker)
        assert "apt" not in names
        assert "snap" not in names

    def test_linux_does_not_include_darwin_entries(self, mocker) -> None:
        names = _plan_names("linux", mocker)
        for mac_entry in ("brew", "npm-check", "python-packages", "uv", "helm", "mise"):
            assert mac_entry not in names

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
        assert cfg.commands["brew"].steps == (
            ("brew", "update"),
            ("brew", "upgrade"),
            ("brew", "cleanup"),
        )

    def test_npm_check_is_interactive(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.commands["npm-check"].interactive is True

    def test_apt_uses_sudo_argv(self, mocker) -> None:
        mocker.patch("sysup.config.ConfigurationLoader.find_config_files_ranked", return_value=[])
        cfg = load_config()
        assert cfg.commands["apt"].steps == (
            ("sudo", "apt", "update"),
            ("sudo", "apt", "upgrade", "-y"),
            ("sudo", "apt", "autoremove", "-y"),
        )

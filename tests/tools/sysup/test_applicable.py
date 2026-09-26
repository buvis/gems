from __future__ import annotations

from sysup.config import SysupConfig, applicable_commands


def _cfg(commands: dict[str, dict[str, object]]) -> SysupConfig:
    return SysupConfig.model_validate({"commands": commands})


class TestApplicableCommands:
    def test_os_mismatch_is_filtered(self, mocker) -> None:
        mocker.patch("sysup.config.sys.platform", "linux")
        mocker.patch("sysup.config.shutil.which", return_value="/bin/x")
        cfg = _cfg(
            {
                "mac-only": {"when": {"os": "darwin"}, "steps": [["x"]]},
                "linux-only": {"when": {"os": "linux"}, "steps": [["x"]]},
            },
        )
        plan = applicable_commands(cfg)
        assert [n for n, _ in plan] == ["linux-only"]

    def test_missing_check_binary_is_filtered(self, mocker) -> None:
        mocker.patch("sysup.config.sys.platform", "darwin")
        mocker.patch("sysup.config.shutil.which", side_effect=lambda n: None if n == "gone" else "/bin/" + n)
        cfg = _cfg(
            {
                "present": {"when": {"check": "brew"}, "steps": [["brew"]]},
                "absent": {"when": {"check": "gone"}, "steps": [["gone"]]},
            },
        )
        plan = applicable_commands(cfg)
        assert [n for n, _ in plan] == ["present"]

    def test_disabled_is_filtered(self, mocker) -> None:
        mocker.patch("sysup.config.sys.platform", "darwin")
        mocker.patch("sysup.config.shutil.which", return_value="/bin/x")
        cfg = _cfg(
            {
                "on": {"steps": [["x"]]},
                "off": {"enabled": False, "steps": [["x"]]},
            },
        )
        plan = applicable_commands(cfg)
        assert [n for n, _ in plan] == ["on"]

    def test_sorted_by_order_then_name(self, mocker) -> None:
        mocker.patch("sysup.config.sys.platform", "darwin")
        mocker.patch("sysup.config.shutil.which", return_value="/bin/x")
        cfg = _cfg(
            {
                "b": {"order": 10, "steps": [["x"]]},
                "a": {"order": 10, "steps": [["x"]]},
                "z": {"order": 5, "steps": [["x"]]},
            },
        )
        plan = applicable_commands(cfg)
        assert [n for n, _ in plan] == ["z", "a", "b"]

    def test_no_when_always_applies(self, mocker) -> None:
        mocker.patch("sysup.config.sys.platform", "darwin")
        cfg = _cfg({"always": {"use": "pip-outdated"}})
        plan = applicable_commands(cfg)
        assert [n for n, _ in plan] == ["always"]

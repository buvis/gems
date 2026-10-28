from __future__ import annotations

import subprocess

from sysup.capabilities.pipx_python import PipxPython

CONFIG = """[tools]
"pipx:gita" = { version = "latest", uvx_args = "--managed-python --python 3.13" }
"pipx:beets" = { version = "latest", extras = "discogs", uvx_args = "--managed-python --python 3.13" }
"pipx:ruff" = { version = "latest", uvx_args = "--managed-python --python 3.14" }
"pipx:plain" = "latest"
"pipx:legacy" = { version = "latest", uvx_args = "--python 3.12" }
python = "3.14.6"
"""


class TestPipxPython:
    @staticmethod
    def _fake_run(mocker, *, current: str = "3.14.6\n", fail: frozenset[str] = frozenset()):
        """Fake subprocess.run; ``fail`` holds tools whose first reinstall fails."""
        pending = set(fail)

        def run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if argv[1:] == ["current", "python"]:
                return subprocess.CompletedProcess(argv, 0, stdout=current, stderr="")
            if argv[1:3] == ["install", "-f"] and argv[3] in pending:
                pending.discard(argv[3])
                return subprocess.CompletedProcess(argv, 1, stdout="", stderr="no wheel for 3.14")
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        mocker.patch("sysup.capabilities.pipx_python.shutil.which", side_effect=lambda name: f"/bin/{name}")
        return mocker.patch("sysup.capabilities.pipx_python.subprocess.run", side_effect=run)

    def test_moves_stale_pins_to_global_minor_and_reinstalls(self, mocker, tmp_path) -> None:
        config = tmp_path / "config.toml"
        config.write_text(CONFIG)
        mock_run = self._fake_run(mocker)

        steps = list(PipxPython().run(config=str(config)))

        assert [s.success for s in steps] == [True, True]
        assert [s.label for s in steps] == [
            "pipx:gita (python 3.13 -> 3.14)",
            "pipx:beets (python 3.13 -> 3.14)",
        ]
        text = config.read_text()
        assert text.count("--managed-python --python 3.14") == 3
        assert "--managed-python --python 3.13" not in text
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert ["/bin/uv", "python", "install", "3.14"] in calls
        assert ["/bin/mise", "install", "-f", "pipx:gita"] in calls

    def test_moves_stale_pins_in_config_local_sibling(self, mocker, tmp_path) -> None:
        config = tmp_path / "config.toml"
        config.write_text(CONFIG.replace("--python 3.13", "--python 3.14"))
        local = tmp_path / "config.local.toml"
        local.write_text(
            '[tools]\n"pipx:yt-dlp" = { version = "latest", uvx_args = "--managed-python --python 3.13" }\n'
        )
        mock_run = self._fake_run(mocker)

        steps = list(PipxPython().run(config=str(config)))

        assert [s.label for s in steps] == ["pipx:yt-dlp (python 3.13 -> 3.14)"]
        assert steps[0].success is True
        assert "--managed-python --python 3.14" in local.read_text()
        assert "--python 3.13" not in local.read_text()
        assert config.read_text() == CONFIG.replace("--python 3.13", "--python 3.14")
        assert ["/bin/mise", "install", "-f", "pipx:yt-dlp"] in [c.args[0] for c in mock_run.call_args_list]

    def test_leaves_unmanaged_and_current_entries_untouched(self, mocker, tmp_path) -> None:
        config = tmp_path / "config.toml"
        config.write_text(CONFIG)
        mock_run = self._fake_run(mocker)

        list(PipxPython().run(config=str(config)))

        text = config.read_text()
        assert '"pipx:legacy" = { version = "latest", uvx_args = "--python 3.12" }' in text
        assert '"pipx:plain" = "latest"' in text
        reinstalled = [c.args[0][3] for c in mock_run.call_args_list if c.args[0][1:3] == ["install", "-f"]]
        assert "pipx:ruff" not in reinstalled
        assert "pipx:legacy" not in reinstalled

    def test_reverts_pin_when_tool_fails_on_new_minor(self, mocker, tmp_path) -> None:
        config = tmp_path / "config.toml"
        config.write_text(CONFIG)
        mock_run = self._fake_run(mocker, fail=frozenset({"pipx:beets"}))

        steps = list(PipxPython().run(config=str(config)))

        beets = next(s for s in steps if s.label.startswith("pipx:beets"))
        assert beets.success is False
        assert "kept on python 3.13" in beets.message
        assert "no wheel for 3.14" in beets.message
        beets_line = next(line for line in config.read_text().splitlines() if line.startswith('"pipx:beets"'))
        assert beets_line.endswith('uvx_args = "--managed-python --python 3.13" }')
        beets_install = ["/bin/mise", "install", "-f", "pipx:beets"]
        assert [c.args[0] for c in mock_run.call_args_list].count(beets_install) == 2

    def test_all_current_is_a_noop(self, mocker, tmp_path) -> None:
        config = tmp_path / "config.toml"
        config.write_text(CONFIG.replace("--python 3.13", "--python 3.14"))
        mock_run = self._fake_run(mocker)

        steps = list(PipxPython().run(config=str(config)))

        assert steps[0].success is True
        assert "on python 3.14" in steps[0].message
        assert all(c.args[0][1] != "install" for c in mock_run.call_args_list)

    def test_no_global_python_skips_without_touching_config(self, mocker, tmp_path) -> None:
        config = tmp_path / "config.toml"
        config.write_text(CONFIG)
        self._fake_run(mocker, current="")

        steps = list(PipxPython().run(config=str(config)))

        assert steps[0].success is False
        assert "no global mise python" in steps[0].message
        assert config.read_text() == CONFIG

    def test_missing_config_skips(self, mocker, tmp_path) -> None:
        self._fake_run(mocker)

        steps = list(PipxPython().run(config=str(tmp_path / "absent.toml")))

        assert steps[0].success is False
        assert "not found" in steps[0].message

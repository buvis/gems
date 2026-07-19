from __future__ import annotations

import json
import subprocess

from sysup.commands.pip.pip import CommandPip


class TestCommandPip:
    @staticmethod
    def _result(
        args: list[str],
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)

    @staticmethod
    def _patch_no_mise(mocker) -> None:
        """Resolve python3 from PATH, no mise available."""
        mocker.patch(
            "sysup.commands.pip.pip.shutil.which",
            side_effect=lambda name: "/mock/python" if name == "python3" else None,
        )

    def _probe(self) -> subprocess.CompletedProcess[str]:
        return self._result(["/mock/python", "-m", "pip", "--version"], stdout="pip 26.0")

    def test_all_packages_updated(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":"alpha"},{"name":"beta"}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "alpha"]),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "beta"]),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip (python3)" and s.success for s in steps)
        assert any(s.label == "alpha (python3)" and s.success for s in steps)
        assert any(s.label == "beta (python3)" and s.success for s in steps)

    def test_discovers_mise_pythons(self, mocker, tmp_path) -> None:
        """The step targets every mise-managed python, not sysup's own venv."""
        pythons = {}
        for version in ("3.12.13", "3.14.6"):
            bin_dir = tmp_path / version / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "python3").touch()
            pythons[version] = str(bin_dir / "python3")
        mise_json = json.dumps(
            [
                {"version": "3.12.13", "install_path": str(tmp_path / "3.12.13")},
                {"version": "3.14.6", "install_path": str(tmp_path / "3.14.6")},
            ],
        )
        mocker.patch(
            "sysup.commands.pip.pip.shutil.which",
            side_effect=lambda name: "/mock/mise" if name == "mise" else None,
        )
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/mise", "ls", "--json", "python"], stdout=mise_json),
            self._result([pythons["3.12.13"], "-m", "pip", "--version"], stdout="pip 26.0"),
            self._result([pythons["3.12.13"], "-m", "pip", "install", "--upgrade", "pip"]),
            self._result([pythons["3.12.13"], "-m", "pip", "list", "--outdated", "--format=json"], stdout="[]"),
            self._result([pythons["3.14.6"], "-m", "pip", "--version"], stdout="pip 26.0"),
            self._result([pythons["3.14.6"], "-m", "pip", "install", "--upgrade", "pip"]),
            self._result([pythons["3.14.6"], "-m", "pip", "list", "--outdated", "--format=json"], stdout="[]"),
        ]

        steps = CommandPip().execute()

        labels = [s.label for s in steps]
        assert "pip (3.12.13)" in labels
        assert "pip (3.14.6)" in labels
        interpreter_calls = [call_item.args[0][0] for call_item in mock_run.call_args_list[1:]]
        assert set(interpreter_calls) == set(pythons.values())

    def test_interpreter_without_pip_is_skipped(self, mocker, tmp_path) -> None:
        """A uv-built venv python has no pip module; report the skip, touch nothing."""
        bin_dir = tmp_path / "3.14.6" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python3").touch()
        mise_json = json.dumps([{"version": "3.14.6", "install_path": str(tmp_path / "3.14.6")}])
        mocker.patch(
            "sysup.commands.pip.pip.shutil.which",
            side_effect=lambda name: "/mock/mise" if name == "mise" else None,
        )
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/mise", "ls", "--json", "python"], stdout=mise_json),
            self._result(
                [str(bin_dir / "python3"), "-m", "pip", "--version"],
                returncode=1,
                stderr="No module named pip",
            ),
        ]

        steps = CommandPip().execute()

        assert len(steps) == 1
        assert steps[0].success is False
        assert "skipping" in steps[0].message
        assert mock_run.call_count == 2

    def test_no_interpreter_found(self, mocker) -> None:
        mocker.patch("sysup.commands.pip.pip.shutil.which", return_value=None)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")

        steps = CommandPip().execute()

        assert len(steps) == 1
        assert steps[0].success is False
        assert "no python interpreter found" in steps[0].message
        assert mock_run.call_count == 0

    def test_mise_ls_failure_falls_back_to_path_python(self, mocker) -> None:
        mocker.patch(
            "sysup.commands.pip.pip.shutil.which",
            side_effect=lambda name: {"mise": "/mock/mise", "python3": "/mock/python"}.get(name),
        )
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/mise", "ls", "--json", "python"], returncode=1, stderr="mise broken"),
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"], stdout="[]"),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip (python3)" and s.success for s in steps)

    def test_mise_entry_without_python_falls_back(self, mocker, tmp_path) -> None:
        mise_json = json.dumps([{"version": "3.14.6", "install_path": str(tmp_path / "missing")}])
        mocker.patch(
            "sysup.commands.pip.pip.shutil.which",
            side_effect=lambda name: {"mise": "/mock/mise", "python3": "/mock/python"}.get(name),
        )
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._result(["/mock/mise", "ls", "--json", "python"], stdout=mise_json),
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"], stdout="[]"),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip (python3)" and s.success for s in steps)

    def test_pip_upgrade_fails(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"], returncode=1, stderr="nope"),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout="[]",
            ),
        ]

        steps = CommandPip().execute()

        pip_step = next(s for s in steps if s.label == "pip (python3)")
        assert pip_step.success is False
        assert "nope" in pip_step.message
        # Still continues to check outdated
        assert len(steps) >= 2

    def test_no_outdated_packages(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout="[]",
            ),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip packages (python3)" and s.success and "no outdated" in s.message for s in steps)

    def test_outdated_check_fails(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                returncode=2,
                stderr="list failed",
            ),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip outdated (python3)" and not s.success for s in steps)
        assert mock_run.call_count == 3

    def test_individual_package_fails(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":"alpha"},{"name":"beta"}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "alpha"], returncode=1, stderr="bad"),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "beta"]),
        ]

        steps = CommandPip().execute()

        alpha = next(s for s in steps if s.label == "alpha (python3)")
        assert alpha.success is False
        assert "bad" in alpha.message
        assert any(s.label == "beta (python3)" and s.success for s in steps)

    def test_malformed_json(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout="not-json",
            ),
        ]

        steps = CommandPip().execute()

        assert any(s.label == "pip outdated (python3)" and not s.success and "parse" in s.message for s in steps)

    def test_uses_discovered_interpreter(self, mocker) -> None:
        """Regression: never pip against sys.executable (sysup's venv has no pip)."""
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":"alpha"}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "alpha"]),
        ]

        CommandPip().execute()

        for call_item in mock_run.call_args_list:
            assert call_item.args[0][0] == "/mock/python"

    def test_pip_upgrade_fails_empty_stderr(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"], returncode=1, stderr=""),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout="[]",
            ),
        ]

        steps = CommandPip().execute()

        pip_step = next(s for s in steps if s.label == "pip (python3)")
        assert pip_step.success is False
        assert "unknown error" in pip_step.message

    def test_outdated_check_fails_empty_stderr(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                returncode=1,
                stderr="",
            ),
        ]

        steps = CommandPip().execute()

        outdated_step = next(s for s in steps if s.label == "pip outdated (python3)")
        assert outdated_step.success is False
        assert "unknown error" in outdated_step.message

    def test_skips_invalid_package_names(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":""},{"name":"good"},{"noname":true}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "good"]),
        ]

        steps = CommandPip().execute()

        labels = [s.label for s in steps]
        assert "good (python3)" in labels
        assert "" not in labels

    def test_individual_package_fails_empty_stderr(self, mocker) -> None:
        self._patch_no_mise(mocker)
        mock_run = mocker.patch("sysup.commands.pip.pip.subprocess.run")
        mock_run.side_effect = [
            self._probe(),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "pip"]),
            self._result(
                ["/mock/python", "-m", "pip", "list", "--outdated", "--format=json"],
                stdout='[{"name":"broken"}]',
            ),
            self._result(["/mock/python", "-m", "pip", "install", "--upgrade", "broken"], returncode=1, stderr=""),
        ]

        steps = CommandPip().execute()

        broken = next(s for s in steps if s.label == "broken (python3)")
        assert broken.success is False
        assert "unknown error" in broken.message

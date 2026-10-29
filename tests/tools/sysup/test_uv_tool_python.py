from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sysup.capabilities import CAPABILITIES
from sysup.capabilities.uv_tool_python import UvToolPython


class TestUvToolPython:
    @staticmethod
    def _receipt(root, tool, *, python=None, requirement=None, extra=""):
        directory = root / tool
        directory.mkdir(parents=True)
        requirement = requirement or f'["{tool}"]'
        text = f"[tool]\nrequirements = {requirement}\n"
        if python is not None:
            text += f'python = "{python}"\n'
        path = directory / "uv-receipt.toml"
        path.write_text(text + extra)
        return path

    @staticmethod
    def _venv(root, tool, version, *, key="version_info"):
        (root / tool / "pyvenv.cfg").write_text(f"home = /py/bin\nimplementation = CPython\n{key} = {version}\n")

    @staticmethod
    def _fake_run(
        mocker,
        root,
        *,
        current="3.14.6\n",
        current_code=0,
        directory_code=0,
        directory=None,
        outcomes=None,
        effects=None,
    ):
        pending = {tuple(argv): list(values) for argv, values in (outcomes or {}).items()}
        effects = {tuple(argv): effect for argv, effect in (effects or {}).items()}

        def run(argv, **kwargs):
            assert isinstance(argv, list)
            assert kwargs.get("capture_output") is True
            assert kwargs.get("text") is True
            assert kwargs.get("check") is False
            assert not kwargs.get("shell", False)
            if argv == ["/bin/mise", "current", "python"]:
                assert kwargs.get("cwd") == Path.home()
                return subprocess.CompletedProcess(argv, current_code, current, "")
            if argv == ["/bin/uv", "tool", "dir"]:
                return subprocess.CompletedProcess(
                    argv, directory_code, str(root) if directory is None else directory, ""
                )
            assert argv[:3] in (["/bin/uv", "python", "install"], ["/bin/uv", "tool", "upgrade"])
            if tuple(argv) in effects:
                effects[tuple(argv)]()
            result = pending.get(tuple(argv), [(0, "")]).pop(0)
            if isinstance(result, OSError):
                raise result
            return subprocess.CompletedProcess(argv, result[0], "", result[1])

        mocker.patch("sysup.capabilities.uv_tool_python.shutil.which", side_effect=lambda name: f"/bin/{name}")
        return mocker.patch("sysup.capabilities.uv_tool_python.subprocess.run", autospec=True, side_effect=run)

    @staticmethod
    def _installs(mock_run):
        return [call.args[0] for call in mock_run.call_args_list if call.args[0][1:3] == ["tool", "upgrade"]]

    @pytest.mark.parametrize("target", ["3.10", "3.14"])
    @pytest.mark.parametrize("structured", [False, True])
    def test_pins_unpinned_tool_to_global_minor_and_reinstalls(self, mocker, tmp_path, target, structured) -> None:
        root = tmp_path / "tools"
        requirements = '[{name = "gita", extras = [], specifier = ""}]' if structured else '["gita"]'
        first = self._receipt(root, "gita", requirement=requirements)
        second = self._receipt(root, "gita-extra")
        originals = [first.read_bytes(), second.read_bytes()]
        mock_run = self._fake_run(mocker, root, current=f"{target}.8\n")

        steps = list(UvToolPython().run())

        assert [(step.label, step.success) for step in steps] == [
            (f"gita (python unpinned -> {target})", True),
            (f"gita-extra (python unpinned -> {target})", True),
        ]
        installs = [["/bin/uv", "tool", "upgrade", "--python", target, tool] for tool in ("gita", "gita-extra")]
        assert self._installs(mock_run) == installs
        calls = [call.args[0] for call in mock_run.call_args_list]
        interpreter = ["/bin/uv", "python", "install", target]
        assert calls.count(interpreter) == 1
        assert calls.index(interpreter) < calls.index(installs[0])
        assert [first.read_bytes(), second.read_bytes()] == originals

    @pytest.mark.parametrize(("old", "target"), [("3.9.9", "3.10"), ("3.13.4rc2", "3.14")])
    def test_moves_stale_pin_to_global_minor(self, mocker, tmp_path, old, target) -> None:
        root = tmp_path / "tools"
        self._receipt(root, "zulu", python=old)
        self._receipt(root, "alpha", python=old)
        self._receipt(root, "alpha-current", python=target)
        mock_run = self._fake_run(mocker, root, current=f"{target}.1\n")

        steps = list(UvToolPython().run())

        minor = ".".join(old.split(".")[:2])
        assert [(step.label, step.success) for step in steps] == [
            (f"alpha (python {minor} -> {target})", True),
            (f"zulu (python {minor} -> {target})", True),
        ]
        assert self._installs(mock_run) == [
            ["/bin/uv", "tool", "upgrade", "--python", target, "alpha"],
            ["/bin/uv", "tool", "upgrade", "--python", target, "zulu"],
        ]

    @pytest.mark.parametrize(
        ("pins", "message"),
        [
            (("3.14.1", "3.14.8rc2"), "all uv tools on python 3.14"),
            (("3.14a1", "3.14.0b2"), "all uv tools on python 3.14"),
            (("3.14", "3.15.2"), "all uv tools pinned to python 3.14 or newer"),
            (("3.15", "4.0.1"), "all uv tools pinned to python 3.14 or newer"),
        ],
    )
    def test_leaves_current_pin_untouched(self, mocker, tmp_path, pins, message) -> None:
        root = tmp_path / "tools"
        paths = [self._receipt(root, tool, python=pin) for tool, pin in zip(("gita", "beets"), pins, strict=True)]
        originals = [path.read_bytes() for path in paths]
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert [(step.success, step.message) for step in steps] == [(True, message)]
        assert self._installs(mock_run) == []
        assert ["/bin/uv", "python", "install", "3.14"] not in [call.args[0] for call in mock_run.call_args_list]
        assert [path.read_bytes() for path in paths] == originals

    @pytest.mark.parametrize("old", [None, "3.12", "3.13"])
    @pytest.mark.parametrize("initial", [(1, "no wheel"), (1, "  "), OSError("initial spawn denied")])
    @pytest.mark.parametrize("recovery", [(0, ""), (2, "recovery denied"), OSError("rollback spawn denied")])
    def test_reverts_to_prior_interpreter_when_tool_fails_on_new_minor(
        self, mocker, tmp_path, old, initial, recovery
    ) -> None:
        root = tmp_path / "tools"
        receipt = self._receipt(root, "alpha", python=old)
        original = receipt.read_bytes()
        self._receipt(root, "zulu", python="3.11")
        target = ("/bin/uv", "tool", "upgrade", "--python", "3.14", "alpha")
        rollback = (
            ("/bin/uv", "tool", "upgrade", "--python", old, "alpha") if old else ("/bin/uv", "tool", "upgrade", "alpha")
        )
        mock_run = self._fake_run(mocker, root, outcomes={target: [initial], rollback: [recovery]})

        steps = list(UvToolPython().run())

        assert [(step.label, step.success) for step in steps] == [
            (f"alpha (python {old or 'unpinned'} -> 3.14)", False),
            ("zulu (python 3.11 -> 3.14)", True),
        ]
        diagnostic = str(initial) if isinstance(initial, OSError) else initial[1].strip() or "unknown error"
        assert diagnostic in steps[0].message
        if recovery == (0, ""):
            assert (f"kept on python {old}" if old else "kept unpinned") in steps[0].message
        else:
            assert (f"reinstall on python {old} also failed" if old else "unpinned reinstall also failed") in steps[
                0
            ].message
            assert (str(recovery) if isinstance(recovery, OSError) else recovery[1]) in steps[0].message
            assert "kept" not in steps[0].message
        assert self._installs(mock_run) == [
            list(target),
            list(rollback),
            ["/bin/uv", "tool", "upgrade", "--python", "3.14", "zulu"],
        ]
        assert receipt.read_bytes() == original

    @pytest.mark.parametrize("old", [None, "3.13"])
    def test_restores_receipt_that_failed_move_deleted_before_rolling_back(self, mocker, tmp_path, old) -> None:
        root = tmp_path / "tools"
        receipt = self._receipt(root, "alpha", python=old)
        original = receipt.read_bytes()
        target = ("/bin/uv", "tool", "upgrade", "--python", "3.14", "alpha")
        rollback = (
            ("/bin/uv", "tool", "upgrade", "--python", old, "alpha") if old else ("/bin/uv", "tool", "upgrade", "alpha")
        )
        seen = []
        self._fake_run(
            mocker,
            root,
            outcomes={target: [(1, "sync failed")]},
            effects={target: receipt.unlink, rollback: lambda: seen.append(receipt.read_bytes())},
        )

        steps = list(UvToolPython().run())

        assert [step.success for step in steps] == [False]
        assert seen == [original]
        assert receipt.read_bytes() == original

    def test_reports_unrestorable_receipt_instead_of_rolling_back(self, mocker, tmp_path) -> None:
        root = tmp_path / "tools"
        receipt = self._receipt(root, "alpha", python="3.13")
        target = ("/bin/uv", "tool", "upgrade", "--python", "3.14", "alpha")
        mock_run = self._fake_run(
            mocker, root, outcomes={target: [(1, "sync failed")]}, effects={target: receipt.unlink}
        )
        mocker.patch("sysup.capabilities.uv_tool_python.atomic_write_bytes", side_effect=OSError("disk full"))

        steps = list(UvToolPython().run())

        assert [step.success for step in steps] == [False]
        assert "receipt restore failed: disk full" in steps[0].message
        assert "sync failed" in steps[0].message
        assert self._installs(mock_run) == [list(target)]

    @pytest.mark.parametrize("python", [None, "3.13"])
    @pytest.mark.parametrize(("key", "version"), [("version_info", "3.14.8"), ("version", "3.14.2")])
    def test_skips_tool_whose_environment_is_already_on_target(self, mocker, tmp_path, python, key, version) -> None:
        root = tmp_path / "tools"
        self._receipt(root, "gita", python=python)
        self._venv(root, "gita", version, key=key)
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert [(step.success, step.message) for step in steps] == [(True, "all uv tools on python 3.14")]
        assert self._installs(mock_run) == []

    @pytest.mark.parametrize("cfg", ["3.13.9", None])
    def test_moves_tool_whose_environment_is_not_on_target(self, mocker, tmp_path, cfg) -> None:
        root = tmp_path / "tools"
        self._receipt(root, "gita")
        if cfg:
            self._venv(root, "gita", cfg)
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert [(step.label, step.success) for step in steps] == [("gita (python unpinned -> 3.14)", True)]
        assert self._installs(mock_run) == [["/bin/uv", "tool", "upgrade", "--python", "3.14", "gita"]]

    @pytest.mark.parametrize("kind", ["absent", "empty", "metadata"])
    def test_no_tools_is_a_noop(self, mocker, tmp_path, kind) -> None:
        root = tmp_path / "tools"
        if kind != "absent":
            root.mkdir()
        if kind == "metadata":
            (root / "uv-receipt.toml").write_text("not a tool")
            self._receipt(root, ".gita")
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert [(step.success, step.message) for step in steps] == [(True, "no uv tools installed")]
        assert self._installs(mock_run) == []
        assert not any(call.args[0][1:3] == ["python", "install"] for call in mock_run.call_args_list)
        assert root.exists() is (kind != "absent")

    @pytest.mark.parametrize(("current", "code"), [("", 0), ("system\n", 0), ("python3.14", 0), ("3.14.6", 1)])
    def test_no_global_python_skips(self, mocker, tmp_path, current, code) -> None:
        root = tmp_path / "tools"
        receipt = self._receipt(root, "gita", python="3.13")
        original = receipt.read_bytes()
        mock_run = self._fake_run(mocker, root, current=current, current_code=code)

        steps = list(UvToolPython().run())

        assert [(step.success, step.message) for step in steps] == [(False, "no global mise python version, skipping")]
        assert self._installs(mock_run) == []
        assert receipt.read_bytes() == original

    @pytest.mark.parametrize("missing", ["uv", "mise"])
    def test_missing_uv_or_mise_skips(self, mocker, missing) -> None:
        which = mocker.patch(
            "sysup.capabilities.uv_tool_python.shutil.which",
            side_effect=lambda name: None if name == missing else f"/bin/{name}",
        )
        run = mocker.patch("sysup.capabilities.uv_tool_python.subprocess.run", autospec=True)
        capability = UvToolPython()

        steps = list(capability.run())
        which.side_effect = lambda name: None
        repeated = list(capability.run())

        assert [(step.label, step.success, step.message) for step in steps] == [
            ("uv tool python", False, "uv or mise not found, skipping")
        ]
        assert repeated == steps
        assert [call.args[0] for call in which.call_args_list].count("uv") == 2
        assert [call.args[0] for call in which.call_args_list].count("mise") == 2
        assert run.call_args_list == []

    @pytest.mark.parametrize(
        "receipt",
        [
            "",
            "[tool",
            '[other]\npython = "3.13"\n',
            '[tool]\npython = "3.13"\n',
            "[tool]\nrequirements = []\n",
            '[tool]\nrequirements = ["gita"]\npython = 314\n',
            '[tool]\nrequirements = ["gita"]\npython = false\n',
        ],
    )
    def test_reports_unsafe_receipt_and_continues_without_reinstalling_it(self, mocker, tmp_path, receipt) -> None:
        root = tmp_path / "tools"
        unsafe = self._receipt(root, "gita")
        unsafe.write_text(receipt)
        self._receipt(root, "zulu", python="3.12")
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert [step.success for step in steps] == [False, True]
        assert steps[0].label == "gita"
        assert steps[0].message.endswith(", skipping")
        assert steps[0].message.removesuffix(", skipping").strip()
        assert self._installs(mock_run) == [["/bin/uv", "tool", "upgrade", "--python", "3.14", "zulu"]]
        assert unsafe.read_text() == receipt

    @pytest.mark.parametrize("pin", [None, "3.12"])
    @pytest.mark.parametrize(
        "receipt",
        [
            '[tool]\nrequirements = ["gita"]\n',
            '[tool]\nrequirements = [{name = "GITA"}]\n',
            '[tool]\nrequirements = [{name = "My_tool"}]\n',
            '[tool]\nrequirements = [{name = "gita", extras = [], specifier = ""}]\n',
            '[tool]\nrequirements = ["gita"]\nconstraints = []\noverrides = []\nexcludes = []\n'
            'build-constraint-dependencies = []\noptions = {}\nentrypoints = [{name = "gita", from = "GITA"}]\n',
            '[tool]\nrequirements = [{name = "gita", editable = "/src/gita"}]\n',
            '[tool]\nrequirements = [{name = "gita", extras = ["web"]}]\n',
            '[tool]\nrequirements = [{name = "gita", specifier = ">=1"}]\n',
            '[tool]\nrequirements = [{name = "gita", url = "https://example.org/gita.whl"}]\n',
            '[tool]\nrequirements = [{name = "gita", future = false}]\n',
            '[tool]\nrequirements = ["gita==1.0"]\n',
            '[tool]\nrequirements = ["gita", "beets"]\n',
            '[tool]\nrequirements = ["gita-extra"]\n',
            '[tool]\nrequirements = ["gita"]\nconstraints = ["beets<2"]\n',
            '[tool]\nrequirements = ["gita"]\noverrides = ["beets"]\n',
            '[tool]\nrequirements = ["gita"]\nexcludes = ["beets"]\n',
            '[tool]\nrequirements = ["gita"]\nbuild-constraint-dependencies = ["beets"]\n',
            '[tool]\nrequirements = ["gita"]\noptions = {index = "https://example.org"}\n',
            '[tool]\nrequirements = ["gita"]\nentrypoints = [{name = "gita", from = "gita-extra"}]\n',
            '[tool]\nrequirements = ["gita"]\nfuture = []\n',
            '[tool]\nrequirements = ["gita"]\nfuture = false\n',
        ],
    )
    def test_moves_every_well_formed_receipt_in_place(self, mocker, tmp_path, receipt, pin) -> None:
        root = tmp_path / "tools"
        path = self._receipt(root, "gita")
        path.write_text(receipt + (f'python = "{pin}"\n' if pin else ""))
        original = path.read_bytes()
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert [(step.label, step.success) for step in steps] == [(f"gita (python {pin or 'unpinned'} -> 3.14)", True)]
        assert self._installs(mock_run) == [["/bin/uv", "tool", "upgrade", "--python", "3.14", "gita"]]
        assert path.read_bytes() == original

    @pytest.mark.parametrize(
        "selector",
        [
            "pypy@3.10",
            "cpython@3.14",
            "/bin/python3.14",
            "python3.14",
            ">=3.14",
            "3.14t",
            "3.14.1junk",
            "3.14rc",
            "",
        ],
    )
    def test_rejects_unsupported_selector_without_claiming_all_current(self, mocker, tmp_path, selector) -> None:
        root = tmp_path / "tools"
        self._receipt(root, "gita", python=selector)
        self._receipt(root, "gita-current", python="3.14")
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert len(steps) == 1
        assert steps[0].label == "gita"
        assert steps[0].success is False
        assert "unsupported" in steps[0].message.lower()
        assert self._installs(mock_run) == []

    @pytest.mark.parametrize("failure", [(1, "download denied"), (2, "  ")])
    def test_interpreter_install_failure_stops_all_tool_installs(self, mocker, tmp_path, failure) -> None:
        root = tmp_path / "tools"
        self._receipt(root, "gita", python="3.13")
        self._receipt(root, "beets")
        argv = ("/bin/uv", "python", "install", "3.14")
        mock_run = self._fake_run(mocker, root, outcomes={argv: [failure]})

        steps = list(UvToolPython().run())

        assert [(step.success, step.message) for step in steps] == [
            (False, f"uv python install 3.14 failed: {failure[1].strip() or 'unknown error'}")
        ]
        assert self._installs(mock_run) == []
        assert [call.args[0] for call in mock_run.call_args_list].count(list(argv)) == 1

    @pytest.mark.parametrize(
        ("xdg", "directory_code", "directory"),
        [
            ("custom-data", 1, "/ignored"),
            ("custom-data", 0, " \n"),
            ("", 1, ""),
        ],
    )
    def test_falls_back_to_environment_or_home_for_unavailable_tool_directory(
        self, mocker, tmp_path, monkeypatch, xdg, directory_code, directory
    ) -> None:
        home = tmp_path / "home"
        mocker.patch("sysup.capabilities.uv_tool_python.Path.home", return_value=home)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / xdg) if xdg else "")
        root = tmp_path / xdg / "uv/tools" if xdg else home / ".local/share/uv/tools"
        self._receipt(root, "gita")
        mock_run = self._fake_run(mocker, root, directory_code=directory_code, directory=directory)

        steps = list(UvToolPython().run())

        assert [(step.label, step.success) for step in steps] == [("gita (python unpinned -> 3.14)", True)]
        assert self._installs(mock_run) == [["/bin/uv", "tool", "upgrade", "--python", "3.14", "gita"]]

    def test_missing_receipt_is_visible_and_does_not_prevent_later_tool(self, mocker, tmp_path) -> None:
        root = tmp_path / "tools"
        (root / "absent").mkdir(parents=True)
        self._receipt(root, "zulu")
        mock_run = self._fake_run(mocker, root)

        steps = list(UvToolPython().run())

        assert [step.success for step in steps] == [False, True]
        assert steps[0].label == "absent"
        assert "skipping" in steps[0].message
        assert [argv[-1] for argv in self._installs(mock_run)] == ["zulu"]

    def test_unlistable_root_reports_discovery_failure(self, mocker, tmp_path) -> None:
        root = tmp_path / "tools"
        root.mkdir()
        mock_run = self._fake_run(mocker, root)
        original = Path.iterdir

        def iterdir(path):
            if path == root:
                raise PermissionError("tool listing denied")
            return original(path)

        mocker.patch("sysup.capabilities.uv_tool_python.Path.iterdir", autospec=True, side_effect=iterdir)

        steps = list(UvToolPython().run())

        assert len(steps) == 1
        assert steps[0].success is False
        assert "tool listing denied" in steps[0].message
        assert self._installs(mock_run) == []

    def test_bundled_registry_exposes_capability_without_inputs(self) -> None:
        assert isinstance(CAPABILITIES["uv-tool-python"], UvToolPython)
        assert UvToolPython().inputs == {}

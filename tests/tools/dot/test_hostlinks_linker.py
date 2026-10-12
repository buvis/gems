from __future__ import annotations

import importlib
import os
import types
from pathlib import Path

import pytest
from dot.hostlinks import linker
from dot.hostlinks.linker import _create_junction, _is_windows, _read_link, reconcile_links
from dot.hostlinks.manifest import MANIFEST_PATH


def _write_manifest(root: Path, text: str) -> None:
    manifest = root / MANIFEST_PATH
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(text, encoding="utf-8")


class TestIsWindows:
    def test_matches_os_name(self) -> None:
        assert _is_windows() == (os.name == "nt")


class TestReadLink:
    def test_returns_target_of_real_symlink(self, tmp_path: Path) -> None:
        (tmp_path / "src").write_text("x", encoding="utf-8")
        os.symlink("src", tmp_path / "lnk")

        assert _read_link(tmp_path / "lnk") == "src"

    def test_returns_none_for_regular_file(self, tmp_path: Path) -> None:
        (tmp_path / "plain").write_text("x", encoding="utf-8")

        assert _read_link(tmp_path / "plain") is None

    def test_returns_none_for_missing_path(self, tmp_path: Path) -> None:
        assert _read_link(tmp_path / "missing") is None

    def test_strips_extended_length_prefix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(linker.os, "readlink", lambda _path: "\\\\?\\C:\\Users\\me\\src")

        assert _read_link(tmp_path / "lnk") == "C:\\Users\\me\\src"

    def test_keeps_value_without_prefix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(linker.os, "readlink", lambda _path: "C:\\Users\\me\\src")

        assert _read_link(tmp_path / "lnk") == "C:\\Users\\me\\src"

    def test_returns_none_on_value_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(_path: object) -> str:
            raise ValueError("embedded null byte")

        monkeypatch.setattr(linker.os, "readlink", boom)

        assert _read_link(tmp_path / "lnk") is None


class TestCreateJunction:
    def test_delegates_to_winapi_create_junction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, str]] = []
        fake_winapi = types.SimpleNamespace(CreateJunction=lambda s, t: calls.append((s, t)))
        real_import = importlib.import_module

        def fake_import(name: str, package: str | None = None) -> types.ModuleType | types.SimpleNamespace:
            if name == "_winapi":
                return fake_winapi
            return real_import(name, package)

        monkeypatch.setattr(importlib, "import_module", fake_import)

        _create_junction("C:\\src", "C:\\dst")

        assert calls == [("C:\\src", "C:\\dst")]


class TestReconcileCreatesLinks:
    def test_links_file_to_absolute_source(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".zshrc => .zshrc.work\n")
        (tmp_path / ".zshrc.work").write_text("work", encoding="utf-8")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked .zshrc"]
        assert problems == []
        assert os.readlink(tmp_path / ".zshrc") == str(tmp_path / ".zshrc.work")
        assert (tmp_path / ".zshrc").read_text(encoding="utf-8") == "work"

    def test_links_directory_to_source_directory(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".cfg => .cfg.work\n")
        (tmp_path / ".cfg.work").mkdir()
        (tmp_path / ".cfg.work" / "a.txt").write_text("a", encoding="utf-8")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked .cfg"]
        assert problems == []
        assert (tmp_path / ".cfg").is_symlink()
        assert (tmp_path / ".cfg" / "a.txt").read_text(encoding="utf-8") == "a"

    def test_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".config/app/conf => conf.host\n")
        (tmp_path / "conf.host").write_text("h", encoding="utf-8")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked .config/app/conf"]
        assert problems == []
        assert (tmp_path / ".config" / "app" / "conf").read_text(encoding="utf-8") == "h"

    def test_rerun_after_linking_returns_nothing(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n.d => .d.host\n")
        (tmp_path / ".a.host").write_text("a", encoding="utf-8")
        (tmp_path / ".d.host").mkdir()
        reconcile_links(tmp_path, apply=True)

        assert reconcile_links(tmp_path, apply=True) == ([], [])

    def test_accepts_equivalent_relative_link_as_current(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, "sub/.a => .a.host\n")
        (tmp_path / ".a.host").write_text("a", encoding="utf-8")
        (tmp_path / "sub").mkdir()
        os.symlink("../.a.host", tmp_path / "sub" / ".a")

        assert reconcile_links(tmp_path, apply=True) == ([], [])

    def test_follows_manifest_order(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, "c => c.h\na => a.h\nb => b.h\n")
        for name in ("a.h", "b.h", "c.h"):
            (tmp_path / name).write_text(name, encoding="utf-8")

        changes, _ = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked c", "linked a", "linked b"]

    def test_relative_root_yields_absolute_links(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        home.mkdir()
        _write_manifest(home, ".a => .a.host\n")
        (home / ".a.host").write_text("a", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        changes, problems = reconcile_links(Path("home"), apply=True)

        assert changes == ["linked .a"]
        assert problems == []
        value = os.readlink(home / ".a")
        assert os.path.isabs(value)
        assert os.path.samefile(value, home / ".a.host")
        assert reconcile_links(Path("home"), apply=True) == ([], [])


class TestReconcileLeavesThingsAlone:
    def test_existing_real_file_is_skipped_with_bytes_intact(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        (tmp_path / ".a.host").write_bytes(b"host")
        (tmp_path / ".a").write_bytes(b"\x00precious\xff")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == [".a: exists and is not a link; skipped"]
        assert not (tmp_path / ".a").is_symlink()
        assert (tmp_path / ".a").read_bytes() == b"\x00precious\xff"

    def test_existing_directory_is_skipped(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        (tmp_path / ".a.host").mkdir()
        (tmp_path / ".a").mkdir()

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == [".a: exists and is not a link; skipped"]
        assert not (tmp_path / ".a").is_symlink()

    def test_link_pointing_elsewhere_is_reported_and_kept(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        (tmp_path / ".a.host").write_text("h", encoding="utf-8")
        (tmp_path / "other").write_text("o", encoding="utf-8")
        os.symlink(str(tmp_path / "other"), tmp_path / ".a")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == [f".a: links to {tmp_path / 'other'}, expected .a.host; skipped"]
        assert os.readlink(tmp_path / ".a") == str(tmp_path / "other")

    def test_dangling_link_is_reported_and_kept(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        os.symlink(str(tmp_path / ".a.host"), tmp_path / ".a")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == [".a: dangling link, no host file at .a.host"]
        assert os.readlink(tmp_path / ".a") == str(tmp_path / ".a.host")

    def test_missing_source_creates_nothing(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, "deep/dir/.a => .a.host\n")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == ["deep/dir/.a: no host file at .a.host"]
        assert not os.path.lexists(tmp_path / "deep" / "dir" / ".a")

    def test_apply_false_reports_missing_link_and_creates_nothing(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, "deep/.a => .a.host\n")
        (tmp_path / ".a.host").write_text("h", encoding="utf-8")

        changes, problems = reconcile_links(tmp_path, apply=False)

        assert changes == []
        assert problems == ["deep/.a: link missing; run 'dot materialize'"]
        assert not os.path.lexists(tmp_path / "deep")

    def test_apply_false_with_current_link_reports_nothing(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        (tmp_path / ".a.host").write_text("h", encoding="utf-8")
        reconcile_links(tmp_path, apply=True)

        assert reconcile_links(tmp_path, apply=False) == ([], [])


class TestReconcileProblems:
    def test_manifest_errors_come_first_and_valid_entries_still_run(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, "broken\n.a => .a.host\n/abs => x\n")
        (tmp_path / ".a.host").write_text("h", encoding="utf-8")

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked .a"]
        assert problems == ["host-links:1: missing '=>'", "host-links:3: absolute path"]

    def test_manifest_errors_precede_entry_problems(self, tmp_path: Path) -> None:
        _write_manifest(tmp_path, ".a => .a.host\nbroken\n")

        _, problems = reconcile_links(tmp_path, apply=True)

        assert problems == ["host-links:2: missing '=>'", ".a: no host file at .a.host"]

    def test_missing_manifest_yields_nothing(self, tmp_path: Path) -> None:
        assert reconcile_links(tmp_path, apply=True) == ([], [])

    def test_posix_symlink_oserror_becomes_problem(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        (tmp_path / ".a.host").write_text("h", encoding="utf-8")
        monkeypatch.setattr(linker, "_is_windows", lambda: False)

        def refuse(*_args: object, **_kwargs: object) -> None:
            raise OSError("disk on fire")

        monkeypatch.setattr(linker.os, "symlink", refuse)

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == [".a: disk on fire"]

    def test_unexpected_oserror_on_one_entry_does_not_stop_the_rest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_manifest(tmp_path, "bad => bad.h\ngood => good.h\n")
        (tmp_path / "bad.h").write_text("b", encoding="utf-8")
        (tmp_path / "good.h").write_text("g", encoding="utf-8")
        real = linker._read_link

        def flaky(path: Path) -> str | None:
            if path.name == "bad":
                raise OSError("flaky disk")
            return real(path)

        monkeypatch.setattr(linker, "_read_link", flaky)

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked good"]
        assert problems == ["bad: flaky disk"]

    def test_unexpected_valueerror_becomes_problem(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_manifest(tmp_path, "bad => bad.h\n")

        def boom(_path: Path) -> str | None:
            raise ValueError("bad value")

        monkeypatch.setattr(linker, "_read_link", boom)

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == ["bad: bad value"]


class TestReconcileWindows:
    def test_directory_source_uses_junction(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_manifest(tmp_path, ".cfg => .cfg.work\n")
        (tmp_path / ".cfg.work").mkdir()
        junctions: list[tuple[str, str]] = []
        symlinks: list[tuple[object, ...]] = []
        monkeypatch.setattr(linker, "_is_windows", lambda: True)
        monkeypatch.setattr(linker, "_create_junction", lambda s, t: junctions.append((s, t)))
        monkeypatch.setattr(linker.os, "symlink", lambda *a, **k: symlinks.append(a))

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked .cfg"]
        assert problems == []
        assert junctions == [(str(tmp_path / ".cfg.work"), str(tmp_path / ".cfg"))]
        assert symlinks == []

    def test_file_source_uses_symlink_not_junction(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        (tmp_path / ".a.host").write_text("h", encoding="utf-8")
        junctions: list[tuple[str, str]] = []
        symlinks: list[tuple[object, ...]] = []
        monkeypatch.setattr(linker, "_is_windows", lambda: True)
        monkeypatch.setattr(linker, "_create_junction", lambda s, t: junctions.append((s, t)))
        monkeypatch.setattr(linker.os, "symlink", lambda *a, **k: symlinks.append(a))

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == ["linked .a"]
        assert problems == []
        assert junctions == []
        assert len(symlinks) == 1
        assert Path(str(symlinks[0][0])) == tmp_path / ".a.host"
        assert Path(str(symlinks[0][1])) == tmp_path / ".a"

    def test_file_symlink_refusal_suggests_developer_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_manifest(tmp_path, ".a => .a.host\n")
        (tmp_path / ".a.host").write_text("h", encoding="utf-8")
        monkeypatch.setattr(linker, "_is_windows", lambda: True)

        def refuse(*_args: object, **_kwargs: object) -> None:
            raise OSError("privilege not held")

        monkeypatch.setattr(linker.os, "symlink", refuse)

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == [".a: symlink refused; enable Developer Mode"]

    def test_junction_oserror_becomes_plain_problem(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_manifest(tmp_path, ".cfg => .cfg.work\n")
        (tmp_path / ".cfg.work").mkdir()
        monkeypatch.setattr(linker, "_is_windows", lambda: True)

        def refuse(_source: str, _target: str) -> None:
            raise OSError("junction failed")

        monkeypatch.setattr(linker, "_create_junction", refuse)

        changes, problems = reconcile_links(tmp_path, apply=True)

        assert changes == []
        assert problems == [".cfg: junction failed"]

    def test_apply_false_creates_no_junction(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_manifest(tmp_path, ".cfg => .cfg.work\n")
        (tmp_path / ".cfg.work").mkdir()
        junctions: list[tuple[str, str]] = []
        monkeypatch.setattr(linker, "_is_windows", lambda: True)
        monkeypatch.setattr(linker, "_create_junction", lambda s, t: junctions.append((s, t)))

        _, problems = reconcile_links(tmp_path, apply=False)

        assert problems == [".cfg: link missing; run 'dot materialize'"]
        assert junctions == []

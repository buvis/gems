from __future__ import annotations

import os
import tarfile
from pathlib import Path

import pytest

from backup.capabilities.tar_archive import TarArchive
from backup.config import BackupConfig
from backup.runner import Runner
from backup.step_result import StepResult


@pytest.fixture(params=["python-tarfile", "system-tar"])
def engine(request: pytest.FixtureRequest) -> str:
    return request.param


def _tree(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _run(source: Path, out: Path, engine: str, items: list[str], **kwargs: object) -> StepResult:
    results = list(
        TarArchive().run(
            label="bundle",
            source=str(source),
            out=str(out),
            engine=engine,
            items=items,
            **kwargs,
        ),
    )
    assert len(results) == 1
    return results[0]


def _members(out: Path) -> list[tarfile.TarInfo]:
    with tarfile.open(out, "r:gz") as archive:
        return archive.getmembers()


def _runner(source: Path, out: Path, engine: str, items: list[str]) -> StepResult:
    cfg = BackupConfig.model_validate(
        {
            "instances": {
                "bundle": {
                    "use": "tar-archive",
                    "with": {
                        "source": str(source),
                        "out": str(out),
                        "engine": engine,
                        "items": items,
                    },
                }
            }
        },
    )
    results = list(Runner(cfg).run([("bundle", cfg.instances["bundle"])]))
    assert len(results) == 1
    return results[0]


class TestBundleItems:
    def test_selected_files_and_directory_use_base_relative_names(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        engine: str,
    ) -> None:
        source = tmp_path / "home"
        _tree(source, {".gitconfig": "git config", ".config/tool/a": "tool content", ".gitconfig-old": "omit"})
        (source / ".config/tool/empty").mkdir()
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.chdir(other)
        out = tmp_path / "bundle.tar.gz"
        result = _run(source, out, engine, [".gitconfig", ".config/tool"])
        assert result.success is True
        assert result.skipped is False
        assert result.file_count == 2
        assert result.total_bytes == len("git config") + len("tool content")
        members = {member.name: member for member in _members(out)}
        assert set(members) == {".gitconfig", ".config/tool", ".config/tool/a", ".config/tool/empty"}
        assert members[".config/tool/empty"].isdir()
        with tarfile.open(out, "r:gz") as archive:
            assert archive.extractfile(".gitconfig").read() == b"git config"
            assert archive.extractfile(".config/tool/a").read() == b"tool content"

    def test_normalization_deduplicates_selected_ancestors_without_prefix_collisions(
        self,
        tmp_path: Path,
        engine: str,
    ) -> None:
        source = tmp_path / "src"
        _tree(source, {"a/b": "first", "ab/b": "second", "abc/b": "unselected"})
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, ["a/b", "a/./", "a//b", "a", "ab/b"])
        names = [member.name for member in _members(out)]
        assert result.success is True
        assert result.file_count == 2
        assert sorted(names) == ["a", "a/b", "ab/b"]

    def test_items_are_literal_paths_without_glob_expansion(self, tmp_path: Path, engine: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"*.txt": "literal", "other.txt": "unselected", "keep": "also selected"})
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, ["*.txt", "keep"])
        assert result.success is True
        assert {member.name for member in _members(out)} == {"*.txt", "keep"}

    @pytest.mark.parametrize("item", ["", "/etc", ".", "a/..", "..", "../x", "..hidden"])
    def test_invalid_item_fails_without_replacing_output(self, tmp_path: Path, engine: str, item: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"keep": "data"})
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous")
        result = _run(source, out, engine, ["keep", item])
        assert result.success is False
        assert result.skipped is False
        assert result.message == f"invalid item '{item}': must be a relative path inside the source"
        assert out.read_bytes() == b"previous"

    def test_explicitly_empty_items_fails(self, tmp_path: Path, engine: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"keep": "data"})
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, [])
        assert result.success is False
        assert result.skipped is False
        assert result.message == "items must not be empty"
        assert not out.exists()

    def test_missing_items_are_listed_while_present_items_are_archived(self, tmp_path: Path, engine: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"a": "first", "b": "second", "missing-extra": "not selected"})
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, ["a", "missing", "b", "absent"])
        assert result.success is True
        assert result.skipped is False
        assert result.message.endswith("; missing items: missing, absent")
        assert {member.name for member in _members(out)} == {"a", "b"}

    def test_parent_symlink_fails_while_final_symlinks_are_preserved(self, tmp_path: Path, engine: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"real/x": "inside"})
        outside = tmp_path / "outside"
        _tree(outside, {"x": "outside", ".bkpignore": "real\n"})
        (source / "link").symlink_to(outside, target_is_directory=True)
        (source / "broken").symlink_to("absent-target")
        out = tmp_path / "out.tar.gz"
        failed = _run(source, out, engine, ["real/x", "link/x"])
        assert failed.success is False
        assert failed.message == "item 'link/x' passes through symlink 'link'"
        assert not out.exists()
        result = _run(source, out, engine, ["link", "broken", "real/x"])
        assert result.success is True
        members = {member.name: member for member in _members(out)}
        assert set(members) == {"link", "broken", "real/x"}
        assert members["link"].issym()
        assert members["link"].linkname == str(outside)
        assert members["broken"].issym()
        assert members["broken"].linkname == "absent-target"
        assert "missing items:" not in result.message

    def test_excludes_match_base_relative_paths_and_basename_without_substring_matching(
        self,
        tmp_path: Path,
        engine: str,
    ) -> None:
        source = tmp_path / "src"
        _tree(
            source,
            {
                "a/secret": "drop",
                "b/secret": "keep",
                "a/secret-old": "keep too",
                "a/cache": "drop",
                "a/cache-old": "retain",
                "b/cache": "drop",
            },
        )
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, ["a", "b"], excludes=["a/secret", "cache"])
        assert result.success is True
        assert {member.name for member in _members(out)} == {"a", "b", "b/secret", "a/secret-old", "a/cache-old"}

    def test_ancestor_and_directory_bkpignore_layers_apply_to_selected_items(
        self,
        tmp_path: Path,
        engine: str,
    ) -> None:
        source = tmp_path / "src"
        _tree(
            source,
            {
                ".bkpignore": "root-secret\n",
                ".config/.bkpignore": "!cache\n",
                ".config/tool/.bkpignore": "private\n",
                ".config/tool/cache/keep": "keep",
                ".config/tool/root-secret": "drop",
                ".config/tool/private": "drop",
                ".config/tool/private-old": "keep",
                "other/cache/drop": "drop",
            },
        )
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, [".config/tool", "other/cache"], excludes=["cache"])
        assert result.success is True
        assert {member.name for member in _members(out)} == {
            ".config/tool",
            ".config/tool/cache",
            ".config/tool/cache/keep",
            ".config/tool/private-old",
        }

    def test_unreadable_selected_file_fails_instead_of_skipping(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        engine: str,
    ) -> None:
        source = tmp_path / "src"
        _tree(source, {"good": "keep", "locked": "cannot read"})
        out = tmp_path / "out.tar.gz"
        out.write_bytes(b"previous")
        real_lstat = os.lstat
        real_stat = os.stat
        real_lexists = os.path.lexists
        checked: set[Path] = set()

        def presence(path: object) -> bool:
            exists = real_lexists(path)
            checked.add(Path(path))
            return exists

        def denied(path: object, *args: object, **kwargs: object) -> os.stat_result:
            if Path(path) == source / "locked" and Path(path) in checked:
                raise PermissionError("fixture permission denied")
            return real_lstat(path, *args, **kwargs)

        def denied_stat(path: object, *args: object, **kwargs: object) -> os.stat_result:
            if Path(path) == source / "locked" and Path(path) in checked:
                raise PermissionError("fixture permission denied")
            return real_stat(path, *args, **kwargs)

        monkeypatch.setattr(os.path, "lexists", presence)
        monkeypatch.setattr(os, "lstat", denied)
        monkeypatch.setattr(os, "stat", denied_stat)
        result = _runner(source, out, engine, ["good", "locked"])
        assert result.success is False
        assert result.skipped is False
        assert "fixture permission denied" in result.message
        assert out.read_bytes() == b"previous"

    def test_file_vanishing_after_presence_check_fails_instead_of_skipping(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        engine: str,
    ) -> None:
        source = tmp_path / "src"
        _tree(source, {"good": "keep", "vanishing": "gone"})
        out = tmp_path / "out.tar.gz"
        real_lexists = os.path.lexists

        def vanish(path: object) -> bool:
            exists = real_lexists(path)
            if Path(path) == source / "vanishing" and exists:
                (source / "vanishing").unlink()
            return exists

        monkeypatch.setattr(os.path, "lexists", vanish)
        result = _runner(source, out, engine, ["good", "vanishing"])
        assert result.success is False
        assert result.skipped is False
        assert "vanishing" in result.message
        assert not out.exists()

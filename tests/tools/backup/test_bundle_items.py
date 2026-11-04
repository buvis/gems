from __future__ import annotations

import os
import tarfile
from datetime import datetime
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

    @pytest.mark.parametrize("item", ["", "/etc", ".", "a/..", "..", "../x"])
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

    @pytest.mark.parametrize("item", ["..", "../x", "a/../../x"])
    def test_traversal_items_are_rejected(self, tmp_path: Path, engine: str, item: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"keep": "data", "..hidden": "literal"})
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, ["keep", item])
        assert result.success is False
        assert result.message == f"invalid item '{item}': must be a relative path inside the source"
        assert not out.exists()

    def test_dot_dot_prefixed_literal_names_are_valid_items(self, tmp_path: Path, engine: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"..hidden": "literal file", "..foo/bar": "inside dir", "..foo-other/x": "unselected"})
        out = tmp_path / "out.tar.gz"
        result = _run(source, out, engine, ["..hidden", "..foo/bar"])
        assert result.success is True
        assert result.skipped is False
        names = {member.name for member in _members(out)}
        assert {"..hidden", "..foo/bar"} <= names
        assert "..foo-other/x" not in names
        with tarfile.open(out, "r:gz") as archive:
            assert archive.extractfile("..hidden").read() == b"literal file"
            assert archive.extractfile("..foo/bar").read() == b"inside dir"

    def test_none_items_archives_whole_tree_like_omitted_items(self, tmp_path: Path, engine: str) -> None:
        source = tmp_path / "src"
        _tree(source, {"a": "first", "d/b": "second"})
        omitted = tmp_path / "omitted.tar.gz"
        explicit = tmp_path / "none.tar.gz"
        common = {"label": "bundle", "source": str(source), "engine": engine}
        (first,) = list(TarArchive().run(out=str(omitted), **common))
        (second,) = list(TarArchive().run(out=str(explicit), items=None, **common))
        assert first.success is True
        assert second.success is True
        assert second.skipped is False
        assert {m.name for m in _members(explicit)} == {m.name for m in _members(omitted)}
        assert {m.name for m in _members(explicit)} >= {"src/a", "src/d/b"}

    @pytest.mark.parametrize("items", [".gitconfig", 5, [".gitconfig", 5], ["keep", None]])
    def test_non_list_items_fail_with_exact_message(self, tmp_path: Path, engine: str, items: object) -> None:
        source = tmp_path / "src"
        _tree(source, {"keep": "data", ".gitconfig": "cfg"})
        out = tmp_path / "out.tar.gz"
        (result,) = list(
            TarArchive().run(label="bundle", source=str(source), out=str(out), engine=engine, items=items),
        )
        assert result.success is False
        assert result.skipped is False
        assert result.message == "items must be a list of relative paths"
        assert not out.exists()

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
        checked: set[Path] = set()

        def denied(path: object, *args: object, **kwargs: object) -> os.stat_result:
            if Path(path) == source / "locked":
                if Path(path) in checked:
                    raise PermissionError("fixture permission denied")
                checked.add(Path(path))
            return real_lstat(path, *args, **kwargs)

        def denied_stat(path: object, *args: object, **kwargs: object) -> os.stat_result:
            if Path(path) == source / "locked" and Path(path) in checked:
                raise PermissionError("fixture permission denied")
            return real_stat(path, *args, **kwargs)

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
        real_lstat = os.lstat

        def vanish(path: object, *args: object, **kwargs: object) -> os.stat_result:
            result = real_lstat(path, *args, **kwargs)
            if Path(path) == source / "vanishing":
                (source / "vanishing").unlink()
            return result

        monkeypatch.setattr(os, "lstat", vanish)
        result = _runner(source, out, engine, ["good", "vanishing"])
        assert result.success is False
        assert result.skipped is False
        assert "vanishing" in result.message
        assert not out.exists()


def _home(root: Path) -> Path:
    home = root / "home"
    _tree(
        home,
        {
            ".gitconfig": "git v1",
            ".npmrc": "npm v1",
            ".gitconfig-old": "omit",
            ".config/sub/f": "sub",
            ".config/tool/t": "tool",
            ".config/tool/deep/f": "deep",
            ".local/keep": "keep",
        },
    )
    return home


def _source_msg(out: Path, source: Path) -> str:
    return f"out path {out} is inside source {source}; choose an out path outside the backup source"


def _item_msg(out: Path, item: Path) -> str:
    return f"out path {out} is inside selected item {item}; choose an out path outside the bundle's items"


def _names(out: Path) -> set[str]:
    return {member.name for member in _members(out)}


class TestBundleOutContainment:
    @pytest.mark.parametrize("out_rel", [".local/backup/settings.tar.gz", "settings.tar.gz"])
    def test_out_under_source_outside_every_item_archives_only_items(
        self, tmp_path: Path, engine: str, out_rel: str
    ) -> None:
        home = _home(tmp_path)
        out = home / out_rel
        result = _run(home, out, engine, [".gitconfig", ".npmrc"])
        assert result.success is True
        assert result.skipped is False
        assert result.file_count == 2
        assert result.out_path == str(out)
        assert _names(out) == {".gitconfig", ".npmrc"}

    def test_rerun_with_existing_out_under_source_succeeds_without_self_member(
        self, tmp_path: Path, engine: str
    ) -> None:
        home = _home(tmp_path)
        out = home / ".local/backup/settings.tar.gz"
        assert _run(home, out, engine, [".gitconfig", ".npmrc"]).success is True
        (home / ".npmrc").write_text("npm v2", encoding="utf-8")
        second = _run(home, out, engine, [".gitconfig", ".npmrc"])
        assert second.success is True
        assert second.skipped is False
        assert _names(out) == {".gitconfig", ".npmrc"}
        with tarfile.open(out, "r:gz") as archive:
            assert archive.extractfile(".npmrc").read() == b"npm v2"

    @pytest.mark.parametrize(
        ("items", "out_rel", "item_rel"),
        [
            ([".config"], ".config/x.tar.gz", ".config"),
            ([".config"], ".config/sub/x.tar.gz", ".config"),
            ([".config"], ".config", ".config"),
            ([".gitconfig"], ".gitconfig", ".gitconfig"),
            ([".gitconfig", ".config/./tool/"], ".config/tool/x.tar.gz", ".config/tool"),
            ([".config/tool", ".config"], ".config/tool/deep/x.tar.gz", ".config"),
        ],
    )
    def test_out_equal_to_or_inside_selected_item_fails_without_writing(
        self, tmp_path: Path, engine: str, items: list[str], out_rel: str, item_rel: str
    ) -> None:
        home = _home(tmp_path)
        out = home / out_rel
        if not out.exists():
            out.write_bytes(b"previous")
        before = {path: path.read_bytes() for path in home.rglob("*") if path.is_file()}
        listing = sorted(home.rglob("*"))
        result = _run(home, out, engine, items)
        assert result.success is False
        assert result.skipped is False
        assert result.message == _item_msg(out, home / item_rel)
        assert sorted(home.rglob("*")) == listing
        assert {path: path.read_bytes() for path in home.rglob("*") if path.is_file()} == before

    @pytest.mark.parametrize("items", [[".gitconfig"], [".config", ".npmrc"]])
    def test_out_equal_to_source_keeps_source_message_with_items(
        self, tmp_path: Path, engine: str, items: list[str]
    ) -> None:
        home = _home(tmp_path)
        result = _run(home, home, engine, items)
        assert result.success is False
        assert result.message == _source_msg(home, home)
        assert home.is_dir()
        assert (home / ".gitconfig").read_text(encoding="utf-8") == "git v1"

    @pytest.mark.parametrize(
        ("items", "out_rel"),
        [
            ([".config"], ".config-backup/x.tar.gz"),
            ([".config"], ".configx.tar.gz"),
            ([".gitconfig", ".config/tool"], ".config/sub/x.tar.gz"),
            ([".gitconfig", ".config/tool"], ".config/tool-backup.tar.gz"),
            ([".config/tool/deep"], ".config/tool/x.tar.gz"),
        ],
    )
    def test_out_under_source_near_an_item_but_outside_it_is_allowed(
        self, tmp_path: Path, engine: str, items: list[str], out_rel: str
    ) -> None:
        home = _home(tmp_path)
        out = home / out_rel
        result = _run(home, out, engine, items)
        assert result.success is True
        names = _names(out)
        assert out.name not in {Path(name).name for name in names}
        assert all(any(name == item or name.startswith(f"{item}/") for item in items) for name in names)
        assert set(items) <= names

    @pytest.mark.parametrize("items_kwargs", [{}, {"items": None}])
    def test_whole_tree_out_under_source_keeps_source_message(
        self, tmp_path: Path, engine: str, items_kwargs: dict[str, object]
    ) -> None:
        home = _home(tmp_path)
        out = home / ".local/backup/all.tar.gz"
        (result,) = list(
            TarArchive().run(label="bundle", source=str(home), out=str(out), engine=engine, **items_kwargs),
        )
        assert result.success is False
        assert result.message == _source_msg(out, home)
        assert not out.exists()

    @pytest.mark.parametrize(
        ("items", "message"),
        [
            ([], "items must not be empty"),
            (["../x"], "invalid item '../x': must be a relative path inside the source"),
            (".gitconfig", "items must be a list of relative paths"),
            ([".gitconfig", None], "items must be a list of relative paths"),
        ],
    )
    def test_invalid_items_win_over_containment(self, tmp_path: Path, engine: str, items: object, message: str) -> None:
        home = _home(tmp_path)
        out = home / ".local/backup/x.tar.gz"
        (result,) = list(TarArchive().run(label="bundle", source=str(home), out=str(out), engine=engine, items=items))
        assert result.success is False
        assert result.message == message
        assert not out.exists()

    def test_symlinked_item_is_archived_as_link_so_out_beside_target_is_allowed(
        self, tmp_path: Path, engine: str
    ) -> None:
        home = _home(tmp_path)
        _tree(home, {"real/f": "target"})
        (home / "link").symlink_to("real", target_is_directory=True)
        out = home / "real/x.tar.gz"
        result = _run(home, out, engine, ["link"])
        assert result.success is True
        members = {member.name: member for member in _members(out)}
        assert set(members) == {"link"}
        assert members["link"].issym()

    def test_out_reached_through_symlinked_parent_is_judged_by_its_real_location(
        self, tmp_path: Path, engine: str
    ) -> None:
        home = _home(tmp_path)
        (home / "alias").symlink_to(home / ".config", target_is_directory=True)
        out = home / "alias/x.tar.gz"
        result = _run(home, out, engine, [".config"])
        assert result.success is False
        assert result.message == _item_msg(out, home / ".config")
        assert not (home / ".config/x.tar.gz").exists()

    def test_stamped_out_basename_under_selected_directory_is_rejected(self, tmp_path: Path, engine: str) -> None:
        home = _home(tmp_path)
        now = datetime(2026, 11, 4, 9, 30)
        out = home / ".config/bk-%Y%m%d.tar.gz"
        result = _run(home, out, engine, [".config"], now=now)
        assert result.success is False
        assert result.message == _item_msg(home / ".config/bk-20261104.tar.gz", home / ".config")
        assert not (home / ".config/bk-20261104.tar.gz").exists()

    def test_stamped_out_basename_outside_items_is_allowed(self, tmp_path: Path, engine: str) -> None:
        home = _home(tmp_path)
        now = datetime(2026, 11, 4, 9, 30)
        out = home / ".local/bk-%Y%m%d-%H%M.tar.gz"
        result = _run(home, out, engine, [".config"], now=now)
        assert result.success is True
        stamped = home / ".local/bk-20261104-0930.tar.gz"
        assert result.out_path == str(stamped)
        assert "bk-20261104-0930.tar.gz" not in {Path(name).name for name in _names(stamped)}

    @pytest.mark.parametrize(("cwd_rel", "allowed"), [(".config", False), (".local", True)])
    def test_relative_out_is_judged_against_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: str, cwd_rel: str, allowed: bool
    ) -> None:
        home = _home(tmp_path)
        monkeypatch.chdir(home / cwd_rel)
        result = _run(home, Path("x.tar.gz"), engine, [".config"])
        assert result.success is allowed
        assert (home / cwd_rel / "x.tar.gz").exists() is allowed

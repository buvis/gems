from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter
from dot.commands.add.add import CommandAdd

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="needs git"),
    pytest.mark.skipif(os.isatty(0), reason="git add -p would wait on the terminal; run without -s"),
]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", f"--git-dir={root}/.buvis", f"--work-tree={root}", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _add(root: Path, path: str):
    return CommandAdd(shell=ShellAdapter(suppress_logging=True), dotfiles_root=str(root), file_path=path).execute()


@pytest.fixture
def bare_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    root = tmp_path / "home"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", "--bare", str(root / ".buvis")], check=True, cwd=root)
    _git(root, "config", "status.showUntrackedFiles", "no")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "user.email", "t@example.com")
    (root / "file1.txt").write_text("one\n")
    (root / ".gitignore").write_text("*.log\n")
    _git(root, "add", "--", "file1.txt", ".gitignore")
    _git(root, "commit", "--quiet", "-m", "init")
    monkeypatch.chdir(root)
    return root


class TestCommandAddIntegration:
    def test_untracked_file_from_nested_cwd_is_staged_whole(self, bare_root: Path, monkeypatch) -> None:
        folder = bare_root / ".config" / "gh-agent"
        folder.mkdir(parents=True)
        (folder / "config.yml").write_text("hello\n")
        monkeypatch.chdir(folder)
        result = _add(bare_root, "config.yml")
        assert result.success is True
        assert result.output == "Currently staged:\nA\t.config/gh-agent/config.yml"
        assert _git(bare_root, "diff", "--cached", "--name-only") == ".config/gh-agent/config.yml"

    def test_bracketed_name_beside_tracked_neighbour_stages_only_the_named_file(self, bare_root: Path) -> None:
        target = bare_root / "file[1].txt"
        target.write_text("new\n")
        (bare_root / "file1.txt").write_text("modified\n")
        result = _add(bare_root, str(target))
        assert result.success is True
        assert result.output == "Currently staged:\nA\tfile[1].txt"
        assert _git(bare_root, "diff", "--cached", "--name-only") == "file[1].txt"
        assert _git(bare_root, "diff", "--name-only") == "file1.txt"

    def test_ignored_file_is_refused_with_rule_and_escape(self, bare_root: Path) -> None:
        (bare_root / "a.log").write_text("ignored\n")
        result = _add(bare_root, "a.log")
        assert result.success is False
        assert ".gitignore:1:*.log" in result.error
        assert "add -f --" in result.error
        assert _git(bare_root, "diff", "--cached", "--name-only") == ""

    def test_tracked_file_without_changes_warns_nothing_staged(self, bare_root: Path) -> None:
        result = _add(bare_root, "file1.txt")
        assert result.success is True
        assert result.warnings == [f"Nothing staged for {bare_root / 'file1.txt'}"]
        assert _git(bare_root, "diff", "--cached", "--name-only") == ""

    def test_tracked_file_with_staged_changes_reports_them_as_currently_staged(self, bare_root: Path) -> None:
        target = bare_root / "file1.txt"
        target.write_text("two\n")
        _git(bare_root, "add", "--", "file1.txt")
        target.write_text("two\nthree\n")
        result = _add(bare_root, "file1.txt")
        assert result.success is True
        assert result.output == "Currently staged:\nM\tfile1.txt"
        assert result.warnings == []
        assert _git(bare_root, "diff", "--cached", "--name-only") == "file1.txt"
        assert _git(bare_root, "diff", "--name-only") == "file1.txt"

    def test_directory_keeps_intent_to_add_flow(self, bare_root: Path) -> None:
        (bare_root / "sub").mkdir()
        (bare_root / "sub" / "new.txt").write_text("new\n")
        result = _add(bare_root, "sub")
        assert result.success is True
        assert _git(bare_root, "ls-files", "--", "sub") == "sub/new.txt"
        assert result.warnings == [f"Nothing staged for {bare_root / 'sub'}"]
        assert _git(bare_root, "diff", "--cached", "--name-only") == ""

    def test_symlink_to_directory_is_staged_as_the_link(self, bare_root: Path) -> None:
        (bare_root / "real").mkdir()
        (bare_root / "real" / "q.txt").write_text("target\n")
        (bare_root / "link").symlink_to("real", target_is_directory=True)
        result = _add(bare_root, "link")
        assert result.success is True
        assert result.output == "Currently staged:\nA\tlink"
        assert _git(bare_root, "diff", "--cached", "--name-only") == "link"
        assert _git(bare_root, "ls-files", "-s", "--", "link").startswith("120000")

    def test_path_outside_the_work_tree_fails_without_staging(self, bare_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "outside.txt"
        target.write_text("outside\n")
        result = _add(bare_root, str(target))
        assert result.success is False
        assert result.error.startswith("Could not determine whether")
        assert _git(bare_root, "diff", "--cached", "--name-only") == ""

"""Two-host real-git tests for the pull divergence save.

Host B edits files in place; host A changes the same files and pushes. B's
pull must save B's edits to a patch that rebuilds them byte for byte, then let
upstream win. ``core.autocrlf=false`` is forced for every git process (and so
every test repository) through ``GIT_CONFIG_*`` environment entries.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from buvis.pybase.adapters.shell.shell import ShellAdapter
from buvis.pybase.result import CommandResult
from dot.commands.pull.pull import CommandPull
from dot.divergence import divergence_dir

from tests.tools.dot.conftest import _disable_git_secret, _git, _run


@pytest.fixture
def no_autocrlf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.autocrlf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "false")


@pytest.fixture
def hosts(no_autocrlf: None, two_host_setup: tuple[Path, Path, Path]) -> tuple[Path, Path, Path]:
    return two_host_setup


def _cmd(host: Path) -> list[str]:
    return _git(host / ".buvis", host)


def _commit_push(host: Path, files: dict[str, bytes], message: str) -> None:
    for name, data in files.items():
        (host / name).write_bytes(data)
    _run([*_cmd(host), "add", *files])
    _run([*_cmd(host), "commit", "-m", message])
    _run([*_cmd(host), "push"])


def _seed(host_a: Path, host_b: Path, files: dict[str, bytes]) -> None:
    _commit_push(host_a, files, "seed")
    _run([*_cmd(host_b), "pull"])


def _head(host: Path) -> str:
    return _run([*_cmd(host), "rev-parse", "HEAD"]).strip()


def _patches(host: Path) -> list[Path]:
    d = divergence_dir(host)
    return sorted(d.glob("*.patch")) if d.is_dir() else []


def _pull(host: Path) -> CommandResult:
    shell = ShellAdapter(suppress_logging=True)
    _disable_git_secret(shell)
    return CommandPull(shell=shell, dotfiles_root=str(host)).execute()


def _apply_at(origin: Path, base: str, patch: Path, dest: Path) -> Path:
    _run(["git", "clone", "--quiet", str(origin), str(dest)])
    _run(["git", "-C", str(dest), "checkout", "--quiet", base])
    _run(["git", "-C", str(dest), "apply", str(patch)])
    return dest


VARIANTS = {
    "text": (b"base\n", b"B edit\n", b"A change\n"),
    "binary": (b"\x00base\xff\x00", b"\x00B edit\xfe\x01\x00", b"\x00A change\x00"),
    "crlf": (b"line1\r\nbase\r\n", b"line1\r\nB edit\r\nline3\r\n", b"line1\r\nA change\r\n"),
}


class TestUpstreamWinsAndPatchRebuildsEdit:
    @pytest.mark.parametrize("variant", list(VARIANTS))
    def test_conflicting_edit_is_saved_then_reset(
        self, hosts: tuple[Path, Path, Path], tmp_path: Path, variant: str
    ) -> None:
        origin, host_a, host_b = hosts
        base, b_edit, a_change = VARIANTS[variant]
        if variant == "crlf":
            assert b"\x00" not in base + b_edit + a_change
        _seed(host_a, host_b, {"x": base})
        (host_b / "x").write_bytes(b_edit)
        _commit_push(host_a, {"x": a_change}, "A changes x")
        b_head = _head(host_b)

        result = _pull(host_b)

        assert result.success, result.error
        assert (host_b / "x").read_bytes() == a_change
        [patch] = _patches(host_b)
        assert f"# base: {b_head}\n".encode() in patch.read_bytes()
        assert result.warnings[:2] == [
            f"divergence patch saved: {patch}",
            "reset to HEAD, local edit in patch: x",
        ]
        rebuilt = _apply_at(origin, b_head, patch, tmp_path / "fresh")
        assert (rebuilt / "x").read_bytes() == b_edit

    def test_dirty_path_untouched_upstream_is_kept_and_not_saved(self, hosts: tuple[Path, Path, Path]) -> None:
        _origin, host_a, host_b = hosts
        _seed(host_a, host_b, {"x": b"x0\n", "y": b"y0\n"})
        (host_b / "x").write_bytes(b"x B\n")
        (host_b / "y").write_bytes(b"y B\n")
        _commit_push(host_a, {"x": b"x A\n"}, "A changes x")

        result = _pull(host_b)

        assert result.success, result.error
        assert (host_b / "y").read_bytes() == b"y B\n"
        [patch] = _patches(host_b)
        assert b"a/y" not in patch.read_bytes()
        assert b"a/x" in patch.read_bytes()

    def test_unpushed_local_commit_is_never_selected(self, hosts: tuple[Path, Path, Path]) -> None:
        _origin, host_a, host_b = hosts
        _seed(host_a, host_b, {"x": b"x0\n", "y": b"y0\n"})
        (host_b / "y").write_bytes(b"y committed on B\n")
        _run([*_cmd(host_b), "commit", "-am", "B changes y"])
        (host_b / "y").write_bytes(b"y dirty on B\n")
        _commit_push(host_a, {"x": b"x A\n"}, "A changes x")

        _pull(host_b)

        assert (host_b / "y").read_bytes() == b"y dirty on B\n"
        assert not any(b"a/y" in p.read_bytes() for p in _patches(host_b))


class TestMixedStateStopsPull:
    @pytest.mark.parametrize("worktree_is_head", [False, True], ids=["worktree-C", "worktree-head"])
    def test_staged_and_unstaged_path_stops_before_any_reset(
        self, hosts: tuple[Path, Path, Path], worktree_is_head: bool
    ) -> None:
        _origin, host_a, host_b = hosts
        _seed(host_a, host_b, {"x": b"x0\n", "z": b"z0\n"})
        (host_b / "x").write_bytes(b"x staged B\n")
        _run([*_cmd(host_b), "add", "x"])
        worktree = b"x0\n" if worktree_is_head else b"x worktree C\n"
        (host_b / "x").write_bytes(worktree)
        (host_b / "z").write_bytes(b"z dirty\n")
        _commit_push(host_a, {"x": b"x A\n", "z": b"z A\n"}, "A changes x and z")
        b_head = _head(host_b)

        result = _pull(host_b)

        assert not result.success
        assert result.error == "pull stopped: x have both staged and unstaged changes; commit or unstage them first"
        assert _run([*_cmd(host_b), "show", ":x"]) == "x staged B\n"
        assert (host_b / "x").read_bytes() == worktree
        assert (host_b / "z").read_bytes() == b"z dirty\n"
        assert _patches(host_b) == []
        assert _head(host_b) == b_head


class TestUntrackedKeptFileStopsPull:
    def test_rm_cached_file_upstream_changed_keeps_disk_bytes(self, hosts: tuple[Path, Path, Path]) -> None:
        _origin, host_a, host_b = hosts
        _seed(host_a, host_b, {"x": b"x0\n"})
        (host_b / "x").write_bytes(b"x B local\n")
        _run([*_cmd(host_b), "rm", "--cached", "--quiet", "x"])
        _commit_push(host_a, {"x": b"x A\n"}, "A changes x")

        result = _pull(host_b)

        assert not result.success
        assert result.error == "pull stopped: x untracked but kept on disk; commit the removal or re-add first"
        assert (host_b / "x").read_bytes() == b"x B local\n"
        assert _patches(host_b) == []


class TestRescuedTargetIsExcluded:
    def test_localized_dirty_target_keeps_b_bytes_at_source(self, hosts: tuple[Path, Path, Path]) -> None:
        from dot.commands.localize.localize import CommandLocalize

        _origin, host_a, host_b = hosts
        (host_b / ".zshrc").write_bytes(b"B dirty zshrc\n")
        localized = CommandLocalize(
            shell=ShellAdapter(suppress_logging=True), dotfiles_root=str(host_a), path=".zshrc"
        ).execute()
        assert localized.success, localized.error
        _run([*_cmd(host_a), "commit", "-m", "Localize .zshrc"])
        _run([*_cmd(host_a), "push"])

        result = _pull(host_b)

        assert result.success, result.error
        assert (host_b / ".local/.zshrc").read_bytes() == b"B dirty zshrc\n"
        assert (host_b / ".zshrc").is_symlink()
        assert not any(b".zshrc" in p.read_bytes() for p in _patches(host_b))


class TestSaveFailureKeepsEdit:
    def test_read_only_divergence_dir_stops_pull_with_edit_intact(self, hosts: tuple[Path, Path, Path]) -> None:
        _origin, host_a, host_b = hosts
        _seed(host_a, host_b, {"x": b"x0\n"})
        (host_b / "x").write_bytes(b"x B\n")
        _commit_push(host_a, {"x": b"x A\n"}, "A changes x")
        b_head = _head(host_b)
        d = divergence_dir(host_b)
        d.mkdir(parents=True)
        d.chmod(0o555)
        try:
            result = _pull(host_b)
        finally:
            d.chmod(0o755)

        assert not result.success
        assert result.error is not None
        assert result.error.startswith("could not save divergence patch: ")
        assert (host_b / "x").read_bytes() == b"x B\n"
        assert _head(host_b) == b_head
        assert _patches(host_b) == []

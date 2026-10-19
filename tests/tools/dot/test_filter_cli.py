"""Tests for the hidden `dot filter` commands and `dot localize --shared`."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from buvis.pybase.result import CommandResult
from dot.cli import cli

TOKEN = b"@HOME@"


def _make_home(tmp_path: Path, name: str) -> Path:
    """Create and return a throwaway host home directory."""
    home = tmp_path / name
    home.mkdir()
    return home


def _encoded(path: Path | str) -> bytes:
    """Return the filesystem bytes of a path."""
    return os.fsencode(str(path))


def _filter_env(
    home: Path,
    *,
    work_tree: str | None = None,
    dotfiles_root: str | None = None,
    extra_bin: Path | None = None,
) -> dict[str, str]:
    """Build a minimal environment for a `dot filter` subprocess."""
    bin_dirs = [str(Path(sys.executable).parent)]
    if extra_bin is not None:
        bin_dirs.insert(0, str(extra_bin))
    return {
        "PATH": os.pathsep.join(bin_dirs),
        "HOME": str(home),
        "DOTFILES_ROOT": str(home) if dotfiles_root is None else dotfiles_root,
        "GIT_WORK_TREE": str(home) if work_tree is None else work_tree,
        "BUVIS_AUTO_UPDATE": "false",
        "LC_ALL": "C.UTF-8",
    }


def _run_filter(
    action: str,
    path_arg: str,
    payload: bytes,
    env: dict[str, str],
    cwd: Path,
) -> subprocess.CompletedProcess[bytes]:
    """Run `dot filter <action> <path>` with byte streams and no shell."""
    return subprocess.run(  # fixed argv, no shell, test-only
        [sys.executable, "-m", "dot", "filter", action, path_arg],
        input=payload,
        env=env,
        cwd=str(cwd),
        capture_output=True,
        check=False,
        timeout=120,
    )


def _sabotage_bin(tmp_path: Path, names: tuple[str, ...]) -> tuple[Path, dict[str, Path]]:
    """Plant shims that leave a sentinel file behind when executed."""
    bin_dir = tmp_path / "sabotage-bin"
    bin_dir.mkdir()
    sentinels = {}
    for name in names:
        sentinel = tmp_path / f"{name}-was-run"
        sentinels[name] = sentinel
        shim = bin_dir / name
        shim.write_text(f'#!/bin/sh\necho "$@" > "{sentinel}"\nexit 0\n')
        shim.chmod(0o755)
    return bin_dir, sentinels


class TestFilterCleanBytes:
    @pytest.mark.parametrize("home_name", ["home-alpha", "beta-home"])
    def test_clean_replaces_every_home_occurrence_with_token(self, tmp_path: Path, home_name: str) -> None:
        home = _make_home(tmp_path, home_name)
        home_bytes = _encoded(home)
        payload = b"first=" + home_bytes + b"/.config/app.conf\nsecond=" + home_bytes + b"/bin/tool\n"

        proc = _run_filter("clean", ".config/app.conf", payload, _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b"first=" + TOKEN + b"/.config/app.conf\nsecond=" + TOKEN + b"/bin/tool\n"
        assert proc.stderr == b""

    def test_clean_leaves_paths_that_only_resemble_home_untouched(self, tmp_path: Path) -> None:
        home = _make_home(tmp_path, "home-alpha")
        home_bytes = _encoded(home)
        base_bytes = _encoded(home.name)
        payload = (
            b"hit=" + home_bytes + b"/x\n"
            b"suffix=" + home_bytes + b"extra/x\n"
            b"prefix=/opt" + home_bytes + b"/x\n"
            b"base=" + base_bytes + b"/x\n"
        )

        proc = _run_filter("clean", ".gitconfig", payload, _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == (
            b"hit=" + TOKEN + b"/x\n"
            b"suffix=" + home_bytes + b"extra/x\n"
            b"prefix=/opt" + home_bytes + b"/x\n"
            b"base=" + base_bytes + b"/x\n"
        )

    def test_clean_passes_an_empty_payload_through(self, tmp_path: Path) -> None:
        home = _make_home(tmp_path, "home-alpha")

        proc = _run_filter("clean", ".gitconfig", b"", _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b""
        assert proc.stderr == b""

    def test_clean_preserves_crlf_bom_and_non_utf8_bytes(self, tmp_path: Path) -> None:
        home = _make_home(tmp_path, "home-alpha")
        home_bytes = _encoded(home)
        payload = b"\xef\xbb\xbfhome=" + home_bytes + b"\r\n\xff\xfe\x00\x01raw\r\n"

        proc = _run_filter("clean", ".config/app.conf", payload, _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b"\xef\xbb\xbfhome=" + TOKEN + b"\r\n\xff\xfe\x00\x01raw\r\n"

    def test_clean_resolves_home_from_work_tree_relative_to_the_working_directory(self, tmp_path: Path) -> None:
        real_tmp = Path(os.path.realpath(tmp_path))
        home = _make_home(real_tmp, "relative-home")
        decoy = _make_home(real_tmp, "decoy-root")
        env = _filter_env(home, work_tree="relative-home", dotfiles_root=str(decoy))
        payload = b"work=" + _encoded(home) + b"/f\ndecoy=" + _encoded(decoy) + b"/f\n"

        proc = _run_filter("clean", ".gitconfig", payload, env, real_tmp)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b"work=" + TOKEN + b"/f\ndecoy=" + _encoded(decoy) + b"/f\n"


class TestFilterCleanTokenRefusal:
    @pytest.mark.parametrize("path_arg", [".gitconfig", "deep/dir/app.conf"])
    def test_clean_refuses_a_payload_that_already_contains_the_token(self, tmp_path: Path, path_arg: str) -> None:
        home = _make_home(tmp_path, "home-alpha")
        payload = b"home=" + TOKEN + b"/x\n"

        proc = _run_filter("clean", path_arg, payload, _filter_env(home), tmp_path)

        assert proc.returncode == 1
        assert proc.stdout == b""
        assert proc.stderr == f"dot filter: {path_arg} already contains @HOME@; the token is reserved\n".encode()


class TestFilterSmudgeBytes:
    @pytest.mark.parametrize("home_name", ["home-alpha", "beta-home"])
    def test_smudge_replaces_every_token_with_the_host_home(self, tmp_path: Path, home_name: str) -> None:
        home = _make_home(tmp_path, home_name)
        home_bytes = _encoded(home)
        payload = b"first=" + TOKEN + b"/.config/app.conf\nsecond=" + TOKEN + b"/bin/tool\n"

        proc = _run_filter("smudge", ".config/app.conf", payload, _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b"first=" + home_bytes + b"/.config/app.conf\nsecond=" + home_bytes + b"/bin/tool\n"
        assert proc.stderr == b""

    def test_smudge_leaves_token_lookalikes_untouched(self, tmp_path: Path) -> None:
        home = _make_home(tmp_path, "home-alpha")
        payload = b"hit=" + TOKEN + b"\nnear=@HOME\nlong=@HOMEX@\nlower=@home@\ntail=HOME@\n"

        proc = _run_filter("smudge", ".gitconfig", payload, _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b"hit=" + _encoded(home) + b"\nnear=@HOME\nlong=@HOMEX@\nlower=@home@\ntail=HOME@\n"

    def test_smudge_passes_an_empty_payload_through(self, tmp_path: Path) -> None:
        home = _make_home(tmp_path, "home-alpha")

        proc = _run_filter("smudge", ".gitconfig", b"", _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b""
        assert proc.stderr == b""

    def test_smudge_preserves_crlf_bom_and_non_utf8_bytes(self, tmp_path: Path) -> None:
        home = _make_home(tmp_path, "home-alpha")
        payload = b"\xef\xbb\xbfhome=" + TOKEN + b"\r\n\xff\xfe\x00\x01raw\r\n"

        proc = _run_filter("smudge", ".config/app.conf", payload, _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b"\xef\xbb\xbfhome=" + _encoded(home) + b"\r\n\xff\xfe\x00\x01raw\r\n"

    def test_smudge_accepts_a_payload_that_also_holds_a_literal_home_path(self, tmp_path: Path) -> None:
        home = _make_home(tmp_path, "home-alpha")
        home_bytes = _encoded(home)
        payload = b"token=" + TOKEN + b"/x\nliteral=" + home_bytes + b"/y\n"

        proc = _run_filter("smudge", ".gitconfig", payload, _filter_env(home), tmp_path)

        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == b"token=" + home_bytes + b"/x\nliteral=" + home_bytes + b"/y\n"
        assert proc.stderr == b""


class TestFilterIsolation:
    @pytest.mark.parametrize("action", ["clean", "smudge"])
    def test_filter_runs_no_git_and_no_update_subprocess(self, tmp_path: Path, action: str) -> None:
        home = _make_home(tmp_path, "home-alpha")
        home_bytes = _encoded(home)
        bin_dir, sentinels = _sabotage_bin(tmp_path, ("git", "uv", "pip"))
        env = _filter_env(home, extra_bin=bin_dir)
        payload = home_bytes + b"\n" if action == "clean" else TOKEN + b"\n"
        expected = TOKEN + b"\n" if action == "clean" else home_bytes + b"\n"

        proc = _run_filter(action, ".gitconfig", payload, env, tmp_path)

        assert proc.returncode == 0, proc.stderr
        # Byte-exact stdout also proves no console marker reached the payload stream.
        assert proc.stdout == expected
        assert proc.stderr == b""
        for name, sentinel in sentinels.items():
            assert not sentinel.exists(), f"{name} was executed"


class TestFilterHelpVisibility:
    def test_filter_group_is_hidden_from_the_top_level_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert re.search(r"^\s+localize\b", result.output, re.MULTILINE)
        assert re.search(r"^\s+filter\b", result.output, re.MULTILINE) is None

    def test_filter_own_help_lists_clean_and_smudge(self, runner) -> None:
        result = runner.invoke(cli, ["filter", "--help"])

        assert result.exit_code == 0
        assert re.search(r"^\s+clean\b", result.output, re.MULTILINE)
        assert re.search(r"^\s+smudge\b", result.output, re.MULTILINE)


class TestLocalizeSharedDispatch:
    @pytest.mark.parametrize(
        ("dotfiles_root", "path_arg"),
        [("/fake/root-one", ".ssh/config"), ("/other/root-two", ".gitconfig")],
    )
    def test_shared_dispatches_to_command_share(
        self,
        monkeypatch,
        mocker,
        runner,
        dotfiles_root: str,
        path_arg: str,
    ) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", dotfiles_root)
        mock_shell = mocker.patch("dot.cli.ShellAdapter")
        mock_share = mocker.patch("dot.commands.localize.share.CommandShare")
        mock_share.return_value.execute.return_value = CommandResult(success=True, output=f"shared {path_arg}")
        mock_localize = mocker.patch("dot.commands.localize.localize.CommandLocalize")

        result = runner.invoke(cli, ["localize", "--shared", path_arg])

        assert result.exit_code == 0, result.output
        assert f"shared {path_arg}" in result.output
        kwargs = mock_share.call_args.kwargs
        assert kwargs["dotfiles_root"] == dotfiles_root
        assert str(kwargs["path"]) == path_arg
        assert kwargs["shell"] is mock_shell.return_value
        assert "source" not in kwargs
        mock_localize.assert_not_called()

    def test_plain_localize_still_dispatches_to_command_localize(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", "/fake/root-one")
        mocker.patch("dot.cli.ShellAdapter")
        mock_share = mocker.patch("dot.commands.localize.share.CommandShare")
        mock_localize = mocker.patch("dot.commands.localize.localize.CommandLocalize")
        mock_localize.return_value.execute.return_value = CommandResult(success=True, output="localized .bashrc")

        result = runner.invoke(cli, ["localize", ".bashrc"])

        assert result.exit_code == 0, result.output
        kwargs = mock_localize.call_args.kwargs
        assert kwargs["dotfiles_root"] == "/fake/root-one"
        assert str(kwargs["path"]) == ".bashrc"
        assert kwargs.get("source") is None
        mock_share.assert_not_called()

    def test_to_option_still_passes_the_source_to_command_localize(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", "/other/root-two")
        mocker.patch("dot.cli.ShellAdapter")
        mock_share = mocker.patch("dot.commands.localize.share.CommandShare")
        mock_localize = mocker.patch("dot.commands.localize.localize.CommandLocalize")
        mock_localize.return_value.execute.return_value = CommandResult(success=True, output="localized .zshrc")

        result = runner.invoke(cli, ["localize", "--to", ".host-config/.zshrc", ".zshrc"])

        assert result.exit_code == 0, result.output
        kwargs = mock_localize.call_args.kwargs
        assert kwargs["dotfiles_root"] == "/other/root-two"
        assert str(kwargs["path"]) == ".zshrc"
        assert str(kwargs["source"]) == ".host-config/.zshrc"
        mock_share.assert_not_called()

    def test_shared_with_to_is_refused_before_any_dispatch(self, monkeypatch, mocker, runner) -> None:
        monkeypatch.setenv("DOTFILES_ROOT", "/fake/root-one")
        mocker.patch("dot.cli.ShellAdapter")
        mock_share = mocker.patch("dot.commands.localize.share.CommandShare")
        mock_localize = mocker.patch("dot.commands.localize.localize.CommandLocalize")

        result = runner.invoke(cli, ["localize", "--shared", "--to", ".host-config/.zshrc", ".zshrc"])

        assert result.exit_code == 1
        assert "--shared cannot be combined with --to" in result.output
        mock_share.assert_not_called()
        mock_localize.assert_not_called()

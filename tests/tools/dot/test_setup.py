from __future__ import annotations

import shlex
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from buvis.pybase.result import CommandResult
from dot.commands.setup.setup import CommandSetup
from dot.git.service import DotGitService

URL = "https://example.test/dots.git"
MATERIALIZE_PATH = "dot.commands.setup.setup.CommandMaterialize"


def scripted_shell(responses: dict[str, tuple[str, str]] | None = None) -> MagicMock:
    """Build a shell whose exe() answers by command prefix, defaulting to success."""
    table = {"cfg rev-parse --abbrev-ref HEAD": ("", "master\n"), **(responses or {})}

    def exe(command: str, _cwd: Path | None = None) -> tuple[str, str]:
        for prefix, reply in table.items():
            if command.startswith(prefix):
                return reply
        return ("", "")

    shell = MagicMock()
    shell.exe.side_effect = exe
    return shell


def commands(shell: MagicMock) -> list[str]:
    return [c[0][0] for c in shell.exe.call_args_list]


def index_of(cmds: list[str], needle: str) -> int:
    return next(i for i, c in enumerate(cmds) if needle in c)


@pytest.fixture
def materialize(mocker) -> MagicMock:
    cls = mocker.patch(MATERIALIZE_PATH)
    cls.return_value.execute.return_value = CommandResult(success=True, info=["linked .x"], warnings=["m warn"])
    return cls


class TestCommandSetupRefusals:
    def test_refuses_existing_buvis_dir_before_any_git_call(self, tmp_path: Path, materialize: MagicMock) -> None:
        (tmp_path / ".buvis").mkdir()
        shell = scripted_shell()

        result = CommandSetup(shell, str(tmp_path), URL).execute()

        assert not result.success
        assert result.error == f"already set up: {tmp_path}/.buvis exists"
        shell.exe.assert_not_called()
        materialize.assert_not_called()

    def test_clone_error_fails_without_further_git_calls(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell({"git clone": ("fatal: nope", "")})

        result = CommandSetup(shell, str(tmp_path), URL).execute()

        assert not result.success
        assert result.error == "clone failed: fatal: nope"
        assert shell.exe.call_count == 1
        materialize.assert_not_called()


class TestCommandSetupCommands:
    def test_clones_bare_with_quoted_url_and_target(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell()

        CommandSetup(shell, str(tmp_path), "file:///a b/dots").execute()

        assert commands(shell)[0] == f"git clone --bare -- 'file:///a b/dots' {shlex.quote(str(tmp_path) + '/.buvis')}"

    def test_clone_treats_dash_leading_url_as_operand_not_option(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell()

        CommandSetup(shell, str(tmp_path), "--upload-pack=touch x").execute()

        assert commands(shell)[0].startswith("git clone --bare -- '--upload-pack=touch x' ")

    def test_self_heal_runs_after_clone_and_before_checkout(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell()

        CommandSetup(shell, str(tmp_path), URL).execute()

        cmds = commands(shell)
        clone = index_of(cmds, "git clone")
        checkout = cmds.index("cfg checkout --no-overwrite-ignore")
        assert clone < index_of(cmds, "remote.origin.fetch") < checkout
        assert clone < index_of(cmds, "core.hooksPath") < checkout

    def test_hides_untracked_files_before_checkout(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell()

        CommandSetup(shell, str(tmp_path), URL).execute()

        cmds = commands(shell)
        assert cmds.index("cfg config status.showUntrackedFiles no") < cmds.index("cfg checkout --no-overwrite-ignore")

    def test_sets_upstream_to_origin_of_head_branch(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell()

        CommandSetup(shell, str(tmp_path), URL).execute()

        cmds = commands(shell)
        fetch = cmds.index("cfg fetch origin")
        rev_parse = cmds.index("cfg rev-parse --abbrev-ref HEAD")
        branch = cmds.index("cfg branch --set-upstream-to=origin/master")
        assert fetch < rev_parse < branch < cmds.index("cfg checkout --no-overwrite-ignore")

    def test_quotes_branch_name_with_shell_metacharacters(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell({"cfg rev-parse --abbrev-ref HEAD": ("", "a;b\n")})

        CommandSetup(shell, str(tmp_path), URL).execute()

        assert "cfg branch '--set-upstream-to=origin/a;b'" in commands(shell)

    def test_never_forces_any_command(self, tmp_path: Path, materialize: MagicMock) -> None:
        happy = scripted_shell()
        conflict = scripted_shell({"cfg checkout": ("error: would be overwritten", "")})
        (tmp_path / "conflict").mkdir()

        CommandSetup(happy, str(tmp_path), URL).execute()
        CommandSetup(conflict, str(tmp_path / "conflict"), URL).execute()

        for shell in (happy, conflict):
            for cmd in commands(shell):
                assert not {"-f", "--force"} & set(shlex.split(cmd))


class TestCommandSetupOutcomes:
    def test_success_reports_clone_checkout_then_materialize_lines(
        self, tmp_path: Path, materialize: MagicMock
    ) -> None:
        result = CommandSetup(scripted_shell(), str(tmp_path), URL).execute()

        assert result.success
        assert result.info == [f"cloned {URL}", "checked out", "linked .x"]
        assert result.warnings == ["m warn"]

    def test_materialize_installs_hooks_with_the_setup_service(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell()

        CommandSetup(shell, str(tmp_path), URL).execute()

        materialize.assert_called_once()
        args, kwargs = materialize.call_args
        assert args == (shell, str(tmp_path))
        assert kwargs["install_hooks"] is True
        assert isinstance(kwargs["git_service"], DotGitService)

    def test_upstream_error_warns_and_setup_continues(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell({"cfg fetch origin": ("fatal: no remote", "")})

        result = CommandSetup(shell, str(tmp_path), URL).execute()

        assert result.success
        assert "upstream not set: fatal: no remote" in result.warnings
        assert "cfg checkout --no-overwrite-ignore" in commands(shell)
        assert not any(c.startswith("cfg branch") for c in commands(shell))
        materialize.return_value.execute.assert_called_once()

    def test_branch_lookup_error_warns_and_setup_continues(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell({"cfg rev-parse --abbrev-ref HEAD": ("fatal: bad head", "")})

        result = CommandSetup(shell, str(tmp_path), URL).execute()

        assert result.success
        assert "upstream not set: fatal: bad head" in result.warnings
        assert "cfg checkout --no-overwrite-ignore" in commands(shell)
        assert not any(c.startswith("cfg branch") for c in commands(shell))
        materialize.return_value.execute.assert_called_once()

    def test_show_untracked_files_error_warns_and_setup_continues(self, tmp_path: Path, materialize: MagicMock) -> None:
        shell = scripted_shell({"cfg config status.showUntrackedFiles": ("error: locked", "")})

        result = CommandSetup(shell, str(tmp_path), URL).execute()

        assert result.success
        assert "status.showUntrackedFiles not set: error: locked" in result.warnings
        assert "cfg checkout --no-overwrite-ignore" in commands(shell)

    def test_checkout_conflict_fails_names_dot_run_checkout_and_skips_materialize(
        self, tmp_path: Path, materialize: MagicMock
    ) -> None:
        shell = scripted_shell({"cfg checkout": ("error: would be overwritten", "")})

        result = CommandSetup(shell, str(tmp_path), URL).execute()

        assert not result.success
        assert result.error == (
            "checkout conflicts with existing files, nothing overwritten:\n"
            "error: would be overwritten\n"
            "move them away, then run: dot run checkout"
        )
        assert result.info == [f"cloned {URL}"]
        materialize.assert_not_called()

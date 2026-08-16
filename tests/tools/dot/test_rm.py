from __future__ import annotations

import shlex
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.commands.rm.rm import CommandRm


def _shell(failing: str = "", error: str = "boom") -> MagicMock:
    """Shell double whose exe fails only for commands containing `failing`."""
    shell = MagicMock()

    def exe(command: str, _cwd: Path) -> tuple[str, str]:
        return (error, "") if failing and failing in command else ("", "")

    shell.exe.side_effect = exe
    return shell


def _issued_commands(shell: MagicMock) -> list[str]:
    return [call.args[0] for call in shell.exe.call_args_list]


def _pathspecs(command: str, subcommands: set[str]) -> list[str]:
    """Tokens a git command acts on: everything but the alias, its subcommands and flags."""
    return [token for token in shlex.split(command)[1:] if token not in subcommands and not token.startswith("-")]


class TestCommandRmIsEncrypted:
    def test_returns_true_when_file_in_secret_list(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", ".secret_file\n.other_file")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        assert cmd._is_encrypted()

    def test_returns_false_when_file_not_in_secret_list(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", ".other_file\n.another_file")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        assert not cmd._is_encrypted()

    def test_returns_false_when_file_is_only_a_prefix_of_a_secret(self, dotfiles_root: Path) -> None:
        # `.env` is not encrypted just because `.env.local` is; treating it as
        # encrypted routes a plain file down the git-secret path.
        shell = MagicMock()
        shell.exe.return_value = ("", ".env.local\n.env.production")
        cmd = CommandRm(shell=shell, file_path=".env")
        assert not cmd._is_encrypted()

    def test_returns_false_when_secret_list_errors(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("git-secret: abort", "")
        cmd = CommandRm(shell=shell, file_path=".secret_file")
        assert not cmd._is_encrypted()
        assert len(cmd.warnings) == 1
        assert "git-secret" in cmd.warnings[0]


class TestCommandRmRemoveNormal:
    def test_removes_from_tracking_with_cached(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")
        cmd = CommandRm(shell=shell, file_path=".config/app.conf")
        result = cmd._remove_normal()
        assert result.success
        shell.exe.assert_called_once_with("cfg rm --cached .config/app.conf", dotfiles_root)

    def test_fails_on_cfg_rm_error(self, dotfiles_root: Path) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("fatal: pathspec did not match", "")
        cmd = CommandRm(shell=shell, file_path=".config/app.conf")
        result = cmd._remove_normal()
        assert not result.success
        assert result.error

    @pytest.mark.parametrize("odd_name", ["my file.txt", "a;rm -rf /"])
    def test_quotes_odd_filename_in_shell_command(self, dotfiles_root: Path, odd_name: str) -> None:
        shell = MagicMock()
        shell.exe.return_value = ("", "")
        cmd = CommandRm(shell=shell, file_path=odd_name)
        result = cmd._remove_normal()
        assert result.success
        shell.exe.assert_any_call(f"cfg rm --cached {shlex.quote(odd_name)}", dotfiles_root)


class TestCommandRmRemoveEncrypted:
    def test_keeps_gitignore_entry_for_surviving_plaintext(self, dotfiles_root: Path) -> None:
        # The plaintext stays on disk, so its ignore entry is the only thing keeping
        # `dot add`/`dot status` from offering a cleartext secret for staging.
        gitignore = dotfiles_root / ".gitignore"
        original = ".aws/credentials\n.aws/credentials_backup\n.other_file\n"
        gitignore.write_text(original)

        shell = _shell()
        cmd = CommandRm(shell=shell, file_path=".aws/credentials")
        result = cmd._remove_encrypted()

        assert result.success
        assert gitignore.read_text() == original
        assert not any(".gitignore" in command for command in _issued_commands(shell))

    def test_keeps_plaintext_file_on_disk(self, dotfiles_root: Path) -> None:
        plaintext = dotfiles_root / ".env.local"
        plaintext.write_text("secret content")

        shell = _shell()
        cmd = CommandRm(shell=shell, file_path=".env.local")
        result = cmd._remove_encrypted()

        assert result.success
        assert plaintext.read_text() == "secret content"

    def test_untracks_ciphertext_from_git(self, dotfiles_root: Path) -> None:
        # `git secret remove` only drops git-secret's mapping; the committed
        # `<file>.secret` stays tracked until it is removed from the index.
        shell = _shell()
        cmd = CommandRm(shell=shell, file_path=".aws/credentials")
        result = cmd._remove_encrypted()

        assert result.success
        untracking = [
            command
            for command in _issued_commands(shell)
            if {"rm", "--cached", ".aws/credentials.secret"} <= set(shlex.split(command))
        ]
        assert len(untracking) == 1
        # The ciphertext is the only pathspec: a wider one would untrack unrelated files.
        assert _pathspecs(untracking[0], subcommands={"rm"}) == [".aws/credentials.secret"]

    def test_stages_gitsecret_mapping_change(self, dotfiles_root: Path) -> None:
        shell = _shell()
        cmd = CommandRm(shell=shell, file_path=".netrc")
        result = cmd._remove_encrypted()

        assert result.success
        staging = [
            command
            for command in _issued_commands(shell)
            if "add" in shlex.split(command)
            and any(token.rstrip("/") == ".gitsecret" for token in shlex.split(command))
        ]
        assert len(staging) == 1
        # Only the mapping directory is staged: staging the work tree would index
        # the plaintext secret that must stay out of git.
        assert [token.rstrip("/") for token in _pathspecs(staging[0], subcommands={"add"})] == [".gitsecret"]

    def test_issues_no_commands_beyond_the_targeted_untracking(self, dotfiles_root: Path) -> None:
        # Backstop for one representative name: any extra command rides along
        # invisibly otherwise (`cfg reset --hard HEAD`, `cfg clean -fdx` would
        # throw away every uncommitted change and untracked file in the work tree).
        file_path = ".aws/credentials"
        shell = _shell()
        cmd = CommandRm(shell=shell, file_path=file_path)
        result = cmd._remove_encrypted()

        assert result.success
        assert _issued_commands(shell) == [
            f"cfg secret remove {shlex.quote(file_path)}",
            f"cfg rm --cached {shlex.quote(file_path + '.secret')}",
            "cfg add .gitsecret/",
        ]

    @pytest.mark.parametrize("file_path", [".secret_file", ".aws/credentials"])
    def test_reports_plaintext_kept_in_success_message(self, dotfiles_root: Path, file_path: str) -> None:
        # The message names the file the user asked about, not a canned one.
        shell = _shell()
        cmd = CommandRm(shell=shell, file_path=file_path)
        result = cmd._remove_encrypted()

        assert result.success
        assert result.output == f"{file_path} removed from git-secret, plaintext kept on disk"

    @pytest.mark.parametrize("error", ["git-secret: abort", "fatal: not a git repository"])
    def test_fails_on_secret_remove_error(self, dotfiles_root: Path, error: str) -> None:
        shell = _shell(failing="secret remove", error=error)
        cmd = CommandRm(shell=shell, file_path=".aws/credentials")
        result = cmd._remove_encrypted()

        assert not result.success
        assert error in result.error
        # The secret is still mapped, so nothing may be untracked or staged after this.
        issued = _issued_commands(shell)
        assert not any("--cached" in shlex.split(command) for command in issued)
        assert not any(".gitsecret" in command for command in issued)

    @pytest.mark.parametrize(
        "error",
        ["fatal: pathspec did not match", "error: unable to write new index file"],
    )
    def test_fails_when_ciphertext_untrack_fails(self, dotfiles_root: Path, error: str) -> None:
        shell = _shell(failing="--cached", error=error)
        cmd = CommandRm(shell=shell, file_path=".netrc")
        result = cmd._remove_encrypted()

        assert not result.success
        assert error in result.error
        # The ciphertext is still tracked, so the mapping change must not be staged.
        assert not any(".gitsecret" in command for command in _issued_commands(shell))

    @pytest.mark.parametrize(
        "error",
        ["fatal: unable to write index", "fatal: pathspec '.gitsecret/' did not match any files"],
    )
    def test_warns_but_succeeds_when_staging_mapping_fails(self, dotfiles_root: Path, error: str) -> None:
        shell = _shell(failing=".gitsecret", error=error)
        cmd = CommandRm(shell=shell, file_path=".env.local")
        result = cmd._remove_encrypted()

        assert result.success
        assert any(error in warning for warning in result.warnings)

    @pytest.mark.parametrize("odd_name", ["my file.txt", "a;rm -rf /"])
    def test_passes_odd_filename_as_single_token_to_every_command(
        self,
        dotfiles_root: Path,
        odd_name: str,
    ) -> None:
        shell = _shell()
        cmd = CommandRm(shell=shell, file_path=odd_name)
        result = cmd._remove_encrypted()

        assert result.success
        referencing = 0
        for command in _issued_commands(shell):
            name_tokens = [token for token in shlex.split(command) if odd_name in token]
            if not name_tokens:
                continue
            referencing += 1
            assert name_tokens in ([odd_name], [f"{odd_name}.secret"])
        # the git-secret removal and the ciphertext untrack, both intact
        assert referencing == 2


class TestCommandRmExecute:
    def test_dispatches_to_encrypted_path(self, dotfiles_root: Path) -> None:
        # Nothing about the name says "secret": only the git-secret listing does,
        # so a dispatch keyed on the filename cannot route this correctly.
        plaintext = dotfiles_root / ".ssh" / "config"
        plaintext.parent.mkdir(parents=True, exist_ok=True)
        plaintext.write_text("secret")

        shell = MagicMock()

        def exe(command: str, _cwd: Path) -> tuple[str, str]:
            # the git-secret list is the only source of truth about encryption
            return ("", ".ssh/config\n.other_secret") if command == "cfg secret list" else ("", "")

        shell.exe.side_effect = exe
        cmd = CommandRm(shell=shell, file_path=".ssh/config")
        result = cmd.execute()

        assert result.success
        # the encrypted branch's own result reaches the caller, not a canned success
        assert result.output == ".ssh/config removed from git-secret, plaintext kept on disk"
        issued = _issued_commands(shell)
        assert "cfg secret list" in issued
        assert "cfg secret remove .ssh/config" in issued
        # the plaintext-untracking command of the normal path must not be issued
        assert "cfg rm --cached .ssh/config" not in issued
        assert plaintext.exists()

    def test_propagates_encrypted_path_failure(self, dotfiles_root: Path) -> None:
        # A user whose `git secret remove` aborted must not be told it worked.
        shell = MagicMock()

        def exe(command: str, _cwd: Path) -> tuple[str, str]:
            if command == "cfg secret list":
                return ("", ".ssh/config\n.other_secret")
            if "secret remove" in command:
                return ("git-secret: abort", "")
            return ("", "")

        shell.exe.side_effect = exe
        cmd = CommandRm(shell=shell, file_path=".ssh/config")
        result = cmd.execute()

        assert not result.success
        assert "git-secret: abort" in result.error

    def test_dispatches_to_normal_path(self, dotfiles_root: Path) -> None:
        shell = MagicMock()

        def exe(command: str, _cwd: Path) -> tuple[str, str]:
            # git-secret knows other files, but not this one
            return ("", ".other_secret\n.yet_another") if command == "cfg secret list" else ("", "")

        shell.exe.side_effect = exe
        cmd = CommandRm(shell=shell, file_path=".config/app.conf")
        result = cmd.execute()

        assert result.success
        issued = _issued_commands(shell)
        assert "cfg secret list" in issued
        assert "cfg rm --cached .config/app.conf" in issued
        assert not any("secret remove" in command for command in issued)

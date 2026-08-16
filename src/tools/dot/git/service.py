from __future__ import annotations

import os
import shlex
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.models import BranchInfo, FileEntry

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter

__all__ = ["DotGitService"]


class DotGitService:
    """Wrap bare-repo git commands for the dotfiles tool."""

    def __init__(self, shell: ShellAdapter, dotfiles_root: str) -> None:
        """Initialize the service.

        Args:
            shell: Shell adapter used to run git commands.
            dotfiles_root: Work-tree root holding the bare ``.buvis`` repository.
        """
        self.shell = shell
        self.dotfiles_root = dotfiles_root
        self.wd = Path(dotfiles_root)
        self._git = f"git --git-dir={dotfiles_root}/.buvis/ --work-tree={dotfiles_root}"
        self.shell.alias("cfg", self._git)
        self._ensure_fetch_refspec()

    def _ensure_fetch_refspec(self) -> None:
        err, out = self.shell.exe("cfg config remote.origin.fetch", self.wd)
        if err or not out or not out.strip():
            self.shell.exe(
                "cfg config remote.origin.fetch +refs/heads/*:refs/remotes/origin/*",
                self.wd,
            )

    def _hide_secrets(self) -> str | None:
        if not self.shell.is_command_available("git-secret"):
            return None
        err, _out = self.shell.exe("cfg secret hide -m", self.wd)
        return err or None

    def status(self) -> tuple[list[FileEntry], str | None]:
        """List changed files.

        Returns:
            The changed files and the error of the secret-hide step, if it failed.
        """
        hide_error = self._hide_secrets()
        err, out = self.shell.exe("cfg status --porcelain", self.wd)
        if err or not out or not out.strip():
            return [], hide_error
        secrets: set[str] = set()
        if self.shell.is_command_available("git-secret"):
            serr, sout = self.shell.exe("cfg secret list", self.wd)
            if not serr and sout:
                secrets = {line for line in sout.strip().split("\n") if line}
        entries: list[FileEntry] = []
        for line in out.split("\n"):
            if len(line) < 3:
                continue
            status_code = line[:2]
            filepath = line[3:]
            entries.append(FileEntry(path=filepath, status=status_code, is_secret=filepath in secrets))
        return entries, hide_error

    def diff(self, path: str, staged: bool = False) -> str:
        """Return the diff of a single file.

        Args:
            path: File path to diff.
            staged: Diff the staged version instead of the worktree one.

        Returns:
            The raw diff text, empty when there is no diff.
        """
        cached = " --cached" if staged else ""
        _err, out = self.shell.exe(f"cfg diff{cached} {shlex.quote(path)}", self.wd)
        return out

    def stage(self, path: str) -> CommandResult:
        """Stage a single path.

        Args:
            path: File path to stage.

        Returns:
            The outcome of the stage command.
        """
        err, _out = self.shell.exe(f"cfg add {shlex.quote(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def commit(self, message: str) -> CommandResult:
        """Hide secrets, then commit the staged changes.

        Args:
            message: Commit message.

        Returns:
            The outcome of the commit command.
        """
        hide_error = self._hide_secrets()
        if hide_error:
            return CommandResult(success=False, error=hide_error)
        err, _out = self.shell.exe(f"cfg commit -m {shlex.quote(message)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def push(self) -> CommandResult:
        """Push local commits when there is anything to push.

        Returns:
            The outcome of the push command.
        """
        if not self._has_unpushed_commits():
            return CommandResult(success=True, output="Nothing to push")
        err, _out = self.shell.exe("cfg push", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True, output="Changes pushed")

    def pull(self, passphrase: str | None = None) -> CommandResult:
        """Pull, refresh submodules and reveal secrets.

        Args:
            passphrase: GPG passphrase for the secret reveal step.

        Returns:
            The outcome of the pull sequence.
        """
        err, _out = self.shell.exe("cfg pull", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        err, _out = self.shell.exe("cfg submodule foreach git reset --hard", self.wd)
        if err:
            return CommandResult(success=False, error=f"Submodule reset failed: {err}")
        err, _out = self.shell.exe("cfg submodule update --init", self.wd)
        if err:
            return CommandResult(success=False, error=f"Submodule init failed: {err}")
        err, _out = self.shell.exe("cfg submodule update --remote --merge", self.wd)
        if err:
            return CommandResult(success=False, error=f"Submodule update failed: {err}")
        if self.shell.is_command_available("git-secret"):
            cmd = "cfg secret reveal -f"
            if passphrase:
                cmd += f" -p {shlex.quote(passphrase)}"
            err, _out = self.shell.exe(cmd, self.wd)
            if err:
                return CommandResult(success=False, error=f"Secret reveal failed: {err}")
        return CommandResult(success=True, output="Dotfiles pulled successfully")

    def has_uncommitted_changes(self) -> bool:
        """Report whether the work-tree has changes to commit."""
        self._hide_secrets()
        err, out = self.shell.exe("cfg status --porcelain", self.wd)
        if err:
            return False
        return bool(out and out.strip())

    def has_unpushed_commits(self) -> bool:
        """Report whether local commits are missing on the remote."""
        return self._has_unpushed_commits()

    def _has_unpushed_commits(self) -> bool:
        err, out = self.shell.exe("cfg rev-list --count @{u}..HEAD", self.wd)
        fell_back = bool(err)
        if fell_back:
            err, out = self.shell.exe(
                f'cfg rev-list --count "origin/$({self._git} rev-parse --abbrev-ref HEAD)..HEAD"',
                self.wd,
            )
            if err:
                # Both lookups failed: assume there may be commits to push.
                return True
        try:
            return int(out.strip()) > 0
        except ValueError:
            return fell_back

    def add_to_gitignore(self, pattern: str) -> CommandResult:
        """Append a pattern to ``.gitignore`` and stage the file.

        Args:
            pattern: Ignore pattern to append.

        Returns:
            The outcome of the write and stage steps.
        """
        try:
            gitignore = self.wd / ".gitignore"
            with gitignore.open("a") as f:
                f.write(f"{pattern}\n")
        except OSError as exc:
            return CommandResult(success=False, error=str(exc))
        return self.stage(".gitignore")

    def _run_patch(self, patch: str, flags: str) -> CommandResult:
        fd, tmpfile = tempfile.mkstemp(suffix=".patch")
        try:
            os.write(fd, patch.encode())
            os.close(fd)
            err, _out = self.shell.exe(f"cfg apply {flags} {tmpfile}", self.wd)
            if err:
                return CommandResult(success=False, error=err)
            return CommandResult(success=True)
        finally:
            if Path(tmpfile).exists():
                os.unlink(tmpfile)

    def apply_patch(self, patch: str) -> CommandResult:
        """Apply a patch to the index.

        Args:
            patch: Patch text.

        Returns:
            The outcome of the apply command.
        """
        return self._run_patch(patch, "--cached")

    def apply_reverse_to_worktree(self, patch: str) -> CommandResult:
        """Reverse-apply a patch to the work-tree.

        Args:
            patch: Patch text.

        Returns:
            The outcome of the apply command.
        """
        return self._run_patch(patch, "--reverse")

    def apply_patch_reverse(self, patch: str) -> CommandResult:
        """Reverse-apply a patch to the index.

        Args:
            patch: Patch text.

        Returns:
            The outcome of the apply command.
        """
        return self._run_patch(patch, "--cached --reverse")

    def branch_info(self) -> BranchInfo:
        """Collect branch name, ahead/behind counts and secret count."""
        name = "unknown"
        ahead = 0
        behind = 0
        secret_count = 0
        err, out = self.shell.exe("cfg rev-parse --abbrev-ref HEAD", self.wd)
        if not err and out and out.strip():
            name = out.strip()
        err, out = self.shell.exe("cfg rev-list --count --left-right @{u}...HEAD", self.wd)
        if err:
            err, out = self.shell.exe(f"cfg rev-list --count --left-right origin/{name}...HEAD", self.wd)
        if not err and out and out.strip():
            parts = out.strip().split("\t")
            if len(parts) == 2:
                try:
                    behind = int(parts[0])
                    ahead = int(parts[1])
                except ValueError:
                    pass
        if self.shell.is_command_available("git-secret"):
            err, out = self.shell.exe("cfg secret list", self.wd)
            if not err and out and out.strip():
                secret_count = len([line for line in out.strip().split("\n") if line])
        return BranchInfo(name=name, ahead=ahead, behind=behind, secret_count=secret_count)

    def ls_files(self, pathspec: str) -> set[str]:
        """List tracked paths matching a pathspec.

        Args:
            pathspec: Pathspec passed to ``git ls-files``.

        Returns:
            The tracked paths, empty when the lookup failed.
        """
        err, out = self.shell.exe(f"cfg ls-files {shlex.quote(pathspec)}", self.wd)
        if err:
            return set()
        return {line for line in out.splitlines() if line}

    def check_ignore(self, pathspec: str) -> set[str]:
        """List ignored paths matching a pathspec.

        Args:
            pathspec: Pathspec passed to ``git check-ignore``.

        Returns:
            The ignored paths, empty when nothing matched.
        """
        err, out = self.shell.exe(f"cfg check-ignore {shlex.quote(pathspec)}", self.wd)
        if err:
            return set()
        return {line for line in out.splitlines() if line}

    def stage_interactive(self, path: str | None = None) -> None:
        """Stage changes interactively, hunk by hunk.

        Args:
            path: Path to stage; the whole work-tree when omitted.
        """
        command = "cfg add -p"
        if path:
            if (self.wd / path).is_dir():
                _err, untracked = self.shell.exe(f"cfg ls-files --others --exclude-standard {path}", self.wd)
                if untracked.strip():
                    self.shell.exe(f"cfg add --intent-to-add {path}", self.wd)
                command = f"cfg add -p {path}"
            else:
                err, _out = self.shell.exe(f"cfg ls-files --error-unmatch {path}", self.wd)
                if "returned non-zero exit status 1" in err:
                    command = f"cfg add {path}"
                else:
                    command = f"cfg add -p {path}"
        self.shell.interact(command, self.wd)

    def unstage(self, path: str | None = None) -> CommandResult:
        """Reset staged changes.

        Args:
            path: Path to unstage; everything staged when omitted.

        Returns:
            The outcome of the reset command.
        """
        if path:
            cmd = f"cfg reset HEAD -- {shlex.quote(path)}"
            msg = f"{path} unstaged"
        else:
            cmd = "cfg reset HEAD"
            msg = "All files unstaged"
        err, _out = self.shell.exe(cmd, self.wd)
        if err:
            return CommandResult(success=False, error=f"Unstage failed: {err}")
        return CommandResult(success=True, output=msg)

    def _is_encrypted(self, path: str, warnings: list[str]) -> bool:
        err, out = self.shell.exe("cfg secret list", self.wd)
        if err:
            warnings.append(f"Could not check git-secret status: {err}")
            return False
        return path in out.splitlines()

    def rm(self, path: str) -> CommandResult:
        """Untrack a path, keeping it on disk.

        Args:
            path: Path to untrack.

        Returns:
            The outcome of the untrack sequence.
        """
        warnings: list[str] = []
        if self._is_encrypted(path, warnings):
            err, _out = self.shell.exe(f"cfg secret remove {shlex.quote(path)}", self.wd)
            if err:
                return CommandResult(success=False, error=f"Failed to remove from git-secret: {err}")
            err, _out = self.shell.exe(f"cfg rm --cached {shlex.quote(path + '.secret')}", self.wd)
            if err:
                return CommandResult(
                    success=False,
                    error=(
                        f"Failed to untrack encrypted file: {err}. "
                        "The git-secret mapping was already changed on disk, so do not simply retry "
                        "the removal: it would take the plaintext path instead. Restore the mapping "
                        "with `cfg checkout -- .gitsecret/` (this discards other unstaged .gitsecret/ "
                        "changes), then retry."
                    ),
                )
            err, _out = self.shell.exe("cfg add .gitsecret/", self.wd)
            if err:
                warnings.append(f"Failed to stage .gitsecret/: {err}")
            return CommandResult(
                success=True,
                output=f"{path} removed from git-secret, plaintext kept on disk",
                warnings=warnings,
            )
        err, _out = self.shell.exe(f"cfg rm --cached {shlex.quote(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=f"Failed to remove: {err}")
        return CommandResult(success=True, output=f"{path} removed from tracking", warnings=warnings)

    def delete(self, path: str) -> CommandResult:
        """Remove a path from the index and from disk.

        Args:
            path: Path to delete.

        Returns:
            The outcome of the delete sequence.
        """
        warnings: list[str] = []
        if self._is_encrypted(path, warnings):
            err, _out = self.shell.exe(f"cfg secret remove -c {path}", self.wd)
            if err:
                return CommandResult(success=False, error=f"Failed to remove from git-secret: {err}")
            gitignore = self.wd / ".gitignore"
            if gitignore.exists():
                lines = gitignore.read_text().splitlines()
                cleaned = [line for line in lines if line != path]
                if len(cleaned) != len(lines):
                    gitignore.write_text(("\n".join(cleaned) + "\n") if cleaned else "")
                    err, _out = self.shell.exe("cfg add .gitignore", self.wd)
                    if err:
                        warnings.append(f"Failed to stage .gitignore: {err}")
            plaintext = self.wd / path
            if plaintext.exists():
                try:
                    plaintext.unlink()
                except OSError as exc:
                    return CommandResult(success=False, error=f"Failed to delete plaintext: {exc}")
            return CommandResult(
                success=True,
                output=f"{path} deleted from git-secret and disk",
                warnings=warnings,
            )
        err, _out = self.shell.exe(f"cfg rm {path}", self.wd)
        if err:
            return CommandResult(success=False, error=f"Failed to delete: {err}")
        return CommandResult(success=True, output=f"{path} deleted from dotfiles", warnings=warnings)

    def encrypt_and_stage(self, path: str) -> CommandResult:
        """Register a path with git-secret, encrypt it and stage the result.

        Args:
            path: Path to encrypt.

        Returns:
            The outcome of the encrypt sequence.
        """
        err, _out = self.shell.exe(f"cfg secret add {path}", self.wd)
        if err:
            return CommandResult(success=False, error=f"Failed to register file: {err}")
        err, _out = self.shell.exe("cfg secret hide -m", self.wd)
        if err:
            return CommandResult(success=False, error=f"Failed to encrypt: {err}")
        err, _out = self.shell.exe(f"cfg add {path}.secret .gitsecret/ .gitignore", self.wd)
        if err:
            return CommandResult(success=False, error=f"Failed to stage: {err}")
        return CommandResult(success=True, output=f"{path} encrypted and staged")

    def is_secret_tool_available(self) -> bool:
        """Report whether ``git-secret`` is installed."""
        return self.shell.is_command_available("git-secret")

    def list_secrets(self) -> list[str]:
        """List the paths registered with git-secret."""
        if not self.is_secret_tool_available():
            return []
        err, out = self.shell.exe("cfg secret list", self.wd)
        if err:
            return []
        return [line.strip() for line in out.splitlines() if line.strip()]

    def register_secret(self, path: str) -> CommandResult:
        """Register a path with git-secret.

        Args:
            path: Path to register.

        Returns:
            The outcome of the register command.
        """
        err, _out = self.shell.exe(f"cfg secret add {shlex.quote(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def unregister_secret(self, path: str) -> CommandResult:
        """Unregister a path from git-secret.

        Args:
            path: Path to unregister.

        Returns:
            The outcome of the unregister command.
        """
        err, _out = self.shell.exe(f"cfg secret remove {shlex.quote(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def reveal_secrets(self, passphrase: str | None = None) -> CommandResult:
        """Decrypt every registered secret.

        Args:
            passphrase: GPG passphrase for the reveal step.

        Returns:
            The outcome of the reveal command.
        """
        cmd = "cfg secret reveal -f"
        if passphrase:
            cmd += f" -p {shlex.quote(passphrase)}"
        err, _out = self.shell.exe(cmd, self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def hide_secrets(self) -> CommandResult:
        """Encrypt every registered secret."""
        err, _out = self.shell.exe("cfg secret hide", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

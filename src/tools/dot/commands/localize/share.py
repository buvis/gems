"""Opt a tracked file into the shared dot-host filter, in place."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.filesystem import atomic_write_text
from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService
from dot.hostfilter import TOKEN, count_home
from dot.hostlinks.manifest import read_manifest

if TYPE_CHECKING:
    from collections.abc import Callable

    from buvis.pybase.adapters.shell.shell import ShellAdapter

    from dot.git.models import IndexEntry

__all__ = ["CommandShare"]

ATTRIBUTES_PATH = ".gitattributes"

_GLOB_CHARS = "*?["
_QUOTE_CHARS = " \t#!\\"
_REGULAR_MODES = frozenset({"100644", "100755"})
_NOT_PLAIN = "{path} is not a plain tracked file (symlink or special mode); shared opt-in refused"
_UNCONFIGURED = (
    "dot-host filter driver is not configured; a prior self-heal write may have failed. "
    "Re-run 'dot status' to retry, then 'dot localize --shared {path}' again"
)


def _has_filter_line(text: str | None, target: str) -> bool:
    """Report whether an active line anchors exactly target to ``filter=dot-host``."""
    anchored = f"/{target}"
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if fields[0] == anchored and "filter=dot-host" in fields[1:]:
            return True
    return False


def _first_refusal(checks: list[tuple[Callable[[], bool], str]]) -> str | None:
    """Return the message of the first check that refuses, evaluating lazily."""
    for failed, message in checks:
        if failed():
            return message
    return None


def _with_note(error: str, restore_error: str | None) -> str:
    """Append a failed attribute-restore note to an error, when there is one."""
    return error if restore_error is None else f"{error}; {restore_error}"


class CommandShare:
    """Register a tracked file with the dot-host filter, leaving it where it is."""

    def __init__(
        self,
        shell: ShellAdapter,
        dotfiles_root: str,
        path: str,
        *,
        git_service: DotGitService | None = None,
    ) -> None:
        """Initialize the share command.

        Args:
            shell: Shell adapter for git commands.
            dotfiles_root: Path to the dotfiles root directory.
            path: Target path ($HOME-relative or absolute under dotfiles root).
            git_service: Optional pre-initialized git service.
        """
        self._shell = shell
        self._root = Path(dotfiles_root)
        self._git_service = git_service or DotGitService(shell, dotfiles_root)

        # Normalize path to dotfiles-relative
        input_path = Path(path)
        if input_path.is_absolute():
            try:
                self._target = str(input_path.relative_to(self._root))
            except ValueError:
                # Path is not under dotfiles root
                self._target = path
        else:
            self._target = path

    def execute(self) -> CommandResult:
        """Run the share command.

        Returns:
            CommandResult with the replaced-value count on success, error on failure.
        """
        target_path = self._root / self._target
        attrs_path = self._root / ATTRIBUTES_PATH
        try:
            previous = self._read_attributes(attrs_path)
            refusal = self._check_before_read(target_path, previous)
            if refusal is not None:
                return CommandResult(success=False, error=refusal)
            data = target_path.read_bytes()
        except (OSError, UnicodeDecodeError) as exc:
            return CommandResult(success=False, error=str(exc))

        refusal = self._check_after_read(data)
        if refusal is not None:
            return CommandResult(success=False, error=refusal)

        # None conflates an absent entry, a conflicted path and a failed read, so refuse
        # rather than hand that None back to restore_index_entry later.
        entry = self._git_service.capture_index_entry(self._target)
        if entry is None:
            return CommandResult(success=False, error=_NOT_PLAIN.format(path=self._target))

        return self._mutate(attrs_path, previous, data, entry)

    def _check_before_read(self, target_path: Path, previous: str | None) -> str | None:
        """Validate everything decidable without the target's bytes.

        The checks run lazily in refusal order, so the first match wins and no
        later git subprocess runs once an earlier check has refused.

        Args:
            target_path: Absolute path of the share target.
            previous: Current attribute-file text, None when the file is absent.

        Returns:
            The refusal message, or None when every check passes.
        """
        checks: list[tuple[Callable[[], bool], str]] = [
            (
                lambda: self._escapes_root(target_path),
                f"{self._target} resolves outside the dotfiles root; shared opt-in refused",
            ),
            (
                lambda: not self._git_service.ls_files(self._target),
                f"{self._target} not tracked; run dot add first",
            ),
            (target_path.is_dir, f"{self._target} is a directory; directory opt-in is unsupported"),
            (
                lambda: self._target in self._git_service.list_secrets(),
                f"{self._target} is a git-secret file; shared opt-in refused",
            ),
            (self._claimed_by_manifest, f"{self._target} already listed in host-links manifest"),
            (
                lambda: self._target == ATTRIBUTES_PATH,
                f"refused: {ATTRIBUTES_PATH} itself cannot be shared",
            ),
            (
                lambda: _has_filter_line(previous, self._target),
                f"{self._target} already has a dot-host filter line",
            ),
            # Before exists(), which follows the link and would blame the broken link on disk.
            (target_path.is_symlink, _NOT_PLAIN.format(path=self._target)),
            (
                lambda: not target_path.exists(),
                f"{self._target} is tracked but missing from disk; run dot add or restore it first",
            ),
        ]
        return _first_refusal(checks)

    def _check_after_read(self, data: bytes) -> str | None:
        """Validate what needs the target's bytes or a further git subprocess.

        Args:
            data: Raw bytes of the share target.

        Returns:
            The refusal message, or None when every check passes.
        """
        checks: list[tuple[Callable[[], bool], str]] = [
            (
                lambda: TOKEN in data,
                f"{self._target} contains the reserved {TOKEN.decode()} token",
            ),
            (
                lambda: any(char in self._target for char in _GLOB_CHARS),
                f"{self._target} looks like a glob pattern; glob opt-in is unsupported",
            ),
            (
                lambda: any(char in self._target for char in _QUOTE_CHARS),
                f"{self._target} needs attribute-file quoting, which is unsupported",
            ),
            (
                lambda: not self._git_service.filter_driver_configured(),
                _UNCONFIGURED.format(path=self._target),
            ),
            (
                lambda: self._index_mode() not in _REGULAR_MODES,
                _NOT_PLAIN.format(path=self._target),
            ),
        ]
        return _first_refusal(checks)

    def _read_attributes(self, attrs_path: Path) -> str | None:
        """Return the attribute-file text, or None when the file does not exist.

        Newline translation is off, so a CRLF attribute file survives a
        rollback byte-exactly instead of coming back with rewritten endings.
        """
        try:
            with attrs_path.open(encoding="utf-8", newline="") as handle:
                return handle.read()
        except FileNotFoundError:
            return None

    def _escapes_root(self, target_path: Path) -> bool:
        """Report whether the target resolves outside the dotfiles root."""
        try:
            resolved = target_path.resolve()
            root = self._root.resolve()
        except OSError:
            return True
        return resolved != root and root not in resolved.parents

    def _claimed_by_manifest(self) -> bool:
        """Report whether a valid host-links entry already claims the target."""
        links, _errors = read_manifest(self._root)
        return any(link.target == self._target for link in links)

    def _index_mode(self) -> str | None:
        """Read the stage-zero index mode of the target, None when unreadable."""
        spec = shlex.quote(f":(literal){self._target}")
        err, out = self._shell.exe(f"cfg ls-files -s -- {spec}", self._root)
        if err:
            return None
        for line in out.splitlines():
            meta, _tab, _name = line.partition("\t")
            fields = meta.split()
            if len(fields) == 3 and fields[2] == "0":
                return fields[0]
        return None

    def _attributes_text(self, previous: str | None) -> str:
        """Return the attribute text with the anchored dot-host line appended."""
        body = previous or ""
        if body and not body.endswith("\n"):
            body += "\n"
        return f"{body}/{self._target} filter=dot-host\n"

    def _mutate(
        self,
        attrs_path: Path,
        previous: str | None,
        data: bytes,
        entry: IndexEntry,
    ) -> CommandResult:
        """Register the attribute, renormalize the target, then stage the attribute file."""
        try:
            atomic_write_text(attrs_path, self._attributes_text(previous))
        except OSError as exc:
            return CommandResult(success=False, error=str(exc))

        effective = self._git_service.check_attr_filter(self._target)
        if effective != "dot-host":
            conflict = (
                f"{self._target} is governed by a conflicting attribute entry "
                f"(effective filter: {effective!r}); check nested .gitattributes files and "
                "$GIT_DIR/info/attributes for a prior rule on this path"
            )
            note = self._restore_attributes(attrs_path, previous)
            return CommandResult(success=False, error=_with_note(conflict, note))

        renormalized = self._git_service.renormalize(self._target)
        if not renormalized.success:
            failure = f"renormalize failed: {renormalized.error}"
            note = self._restore_attributes(attrs_path, previous)
            return CommandResult(success=False, error=_with_note(failure, note))

        staged = self._git_service.stage(ATTRIBUTES_PATH)
        if not staged.success:
            return self._roll_back(attrs_path, previous, entry, staged.error)

        count = count_home(data, str(self._root))
        if count:
            output = f"shared {self._target}: {count} host value(s) replaced"
        else:
            output = f"no host value found in {self._target}; filter active for future writes"
        return CommandResult(success=True, output=output, info=[f"staged {ATTRIBUTES_PATH}"])

    def _roll_back(
        self,
        attrs_path: Path,
        previous: str | None,
        entry: IndexEntry,
        stage_error: str | None,
    ) -> CommandResult:
        """Undo the attribute write and the renormalize, reporting whether it worked."""
        restore_error = self._restore_attributes(attrs_path, previous)
        restored = self._git_service.restore_index_entry(self._target, entry)
        prefix = f"could not stage {ATTRIBUTES_PATH}: {stage_error}"
        index_error = None if restored.success else restored.error
        reasons = [reason for reason in (restore_error, index_error) if reason]
        if reasons:
            return CommandResult(
                success=False,
                error=(
                    f"{prefix}; ROLLBACK FAILED ({'; '.join(reasons)}); "
                    f"{self._target}'s index entry may still be tokenized — run 'cfg status' and "
                    f"'dot run diff --cached -- {self._target}' before retrying"
                ),
            )
        return CommandResult(
            success=False,
            error=f"{prefix}; share rolled back, retry 'dot localize --shared {self._target}'",
        )

    def _restore_attributes(self, attrs_path: Path, previous: str | None) -> str | None:
        """Put the attribute file back as it was, removing one this command created.

        Returns:
            An error string when the restore failed, None when it succeeded.
        """
        try:
            if previous is None:
                attrs_path.unlink(missing_ok=True)
            else:
                atomic_write_text(attrs_path, previous)
        except OSError as exc:
            return f"could not restore {ATTRIBUTES_PATH} ({exc})"
        return None

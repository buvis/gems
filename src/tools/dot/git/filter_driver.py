from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.models import IndexEntry

if TYPE_CHECKING:
    from pathlib import Path

    from buvis.pybase.adapters.shell.shell import ShellAdapter

__all__ = [
    "FILTER_CLEAN_KEY",
    "FILTER_CLEAN_VALUE",
    "FILTER_REQUIRED_KEY",
    "FILTER_SMUDGE_KEY",
    "FILTER_SMUDGE_VALUE",
    "FilterDriverMixin",
]


def _literal(path: str) -> str:
    """Quote a path as a shell-safe literal pathspec (no glob matching)."""
    return shlex.quote(f":(literal){path}")


FILTER_CLEAN_KEY = "filter.dot-host.clean"
FILTER_SMUDGE_KEY = "filter.dot-host.smudge"
FILTER_REQUIRED_KEY = "filter.dot-host.required"
FILTER_CLEAN_VALUE = "BUVIS_AUTO_UPDATE=false dot filter clean -- %f"
FILTER_SMUDGE_VALUE = "BUVIS_AUTO_UPDATE=false dot filter smudge -- %f"


class FilterDriverMixin:
    """The dot-host filter driver surface of the dotfiles git service."""

    shell: ShellAdapter
    wd: Path

    def _config_value(self, key: str) -> str:
        """Read a config value, empty when it is unset or unreadable."""
        err, out = self.shell.exe(f"cfg config {key}", self.wd)
        if err:
            return ""
        return out.strip()

    def _ensure_filter_driver(self) -> None:
        """Configure the dot-host filter driver when its clean command is unset.

        Unsets the keys already written when a later write fails, so the repo
        never keeps a half-configured required filter.
        """
        if self._config_value(FILTER_CLEAN_KEY):
            return
        written: list[str] = []
        for key, value in (
            (FILTER_CLEAN_KEY, FILTER_CLEAN_VALUE),
            (FILTER_SMUDGE_KEY, FILTER_SMUDGE_VALUE),
            (FILTER_REQUIRED_KEY, "true"),
        ):
            err, _out = self.shell.exe(f"cfg config {key} {shlex.quote(value)}", self.wd)
            if err:
                for done in written:
                    self.shell.exe(f"cfg config --unset {done}", self.wd)
                return
            written.append(key)

    def filter_driver_configured(self) -> bool:
        """Report whether the dot-host filter driver is fully configured and required."""
        clean = self._config_value(FILTER_CLEAN_KEY)
        smudge = self._config_value(FILTER_SMUDGE_KEY)
        required = self._config_value(FILTER_REQUIRED_KEY)
        return bool(clean and smudge and required == "true")

    def check_attr_filter(self, path: str) -> str | None:
        """Report the filter attribute in effect for a path.

        Args:
            path: Path to query.

        Returns:
            The effective filter name, or None when it is unspecified or unreadable.
        """
        err, out = self.shell.exe(f"cfg check-attr -z filter -- {shlex.quote(path)}", self.wd)
        if err:
            return None
        fields = out.split("\0")
        if len(fields) < 3:
            return None
        value = fields[2]
        return None if value == "unspecified" else value

    def renormalize(self, path: str) -> CommandResult:
        """Re-stage a path through the configured filters.

        Args:
            path: Path to renormalize.

        Returns:
            The outcome of the renormalize command.
        """
        err, _out = self.shell.exe(f"cfg add --renormalize -- {_literal(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True, output="")

    def capture_index_entry(self, path: str) -> IndexEntry | None:
        """Read the stage-zero index record of a path.

        Pass a file path, not a directory: a literal pathspec also matches
        files under a directory, so a directory argument captures whichever
        contained file git lists first.

        Args:
            path: File path to look up.

        Returns:
            The mode and sha, or None when no stage-zero record could be read.

            None is deliberately NOT "the path is untracked". It covers three
            cases a caller must tell apart itself: the path has no index entry,
            the path is conflicted (stages 1/2/3 only, no stage 0), or the
            ``ls-files`` read failed. A caller that requires a tracked path must
            refuse to mutate on None rather than read it as "was untracked" -
            otherwise the matching ``restore_index_entry(path, None)`` drops a
            real index entry, discarding conflict stages or a tracked entry
            whose read merely failed. Only a caller for which absence is the
            genuinely expected state (a not-yet-tracked ``.gitattributes``) may
            treat None as absence.
        """
        err, out = self.shell.exe(f"cfg ls-files -s -- {_literal(path)}", self.wd)
        if err:
            return None
        for line in out.splitlines():
            meta, _tab, _name = line.partition("\t")
            fields = meta.split()
            if len(fields) == 3 and fields[2] == "0":
                return IndexEntry(mode=fields[0], sha=fields[1])
        return None

    def restore_index_entry(self, path: str, entry: IndexEntry | None) -> CommandResult:
        """Put a captured index record back, or drop the entry when there was none.

        Args:
            path: Path to restore.
            entry: The record ``capture_index_entry`` returned before the
                change. None drops the path from the index, so pass None only
                when the path genuinely had no index entry - never a None that
                came back from a conflicted path or a failed read (see
                ``capture_index_entry``), which would discard real index state.

        Returns:
            The outcome of the index update. Touches only the index; the
            work-tree file is never read or written.
        """
        if entry is None:
            cmd = f"cfg rm --cached --ignore-unmatch -- {_literal(path)}"
        else:
            cacheinfo = shlex.quote(f"{entry.mode},{entry.sha},{path}")
            cmd = f"cfg update-index --add --cacheinfo {cacheinfo}"
        err, _out = self.shell.exe(cmd, self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

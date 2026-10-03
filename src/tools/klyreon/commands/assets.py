"""``klyreon assets`` command classes.

One class per subcommand. Each returns a :class:`CommandResult`; the CLI layer
renders it through ``console.report_result``. No console calls, no process exit
here — command discipline (PRD 00074).
"""

from __future__ import annotations

from buvis.pybase.result import CommandResult

from klyreon.assets import installer
from klyreon.assets.manifest import ManifestError, load_manifest
from klyreon.assets.registry import UnknownOperatorError, known_operator_names

__all__ = [
    "CommandAssetsInstall",
    "CommandAssetsRefresh",
    "CommandAssetsStatus",
    "CommandAssetsUninstall",
]


def _default_operators() -> list[str]:
    """Operators to act on when none are given: those already in the manifest."""
    try:
        manifest = load_manifest()
    except ManifestError:
        return []
    return sorted({e.operator for e in manifest.entries if e.kind == "asset"})


class CommandAssetsInstall:
    """Install (or refresh) one or more operator packs and record them.

    With no operators given, defaults to every operator already in the manifest;
    when the manifest is empty, a choice is required (the CLI reports the error).
    """

    def __init__(self, operators: list[str]) -> None:
        self.operators = operators

    def execute(self) -> CommandResult:
        operators = self.operators or _default_operators()
        if not operators:
            return CommandResult(
                success=False,
                error=(
                    "no operator given and nothing is installed yet. "
                    f"Choose one with --operator (known: {', '.join(known_operator_names())})."
                ),
            )
        try:
            report = installer.install(operators)
        except UnknownOperatorError as exc:
            return CommandResult(success=False, error=str(exc))
        except ManifestError as exc:
            return CommandResult(success=False, error=str(exc))

        info = [f"wrote: {p}" for p in report.written]
        info += [f"current: {p}" for p in report.current]
        warnings = [f"backed up your edit of {orig} to {backup}" for orig, backup in report.displaced]
        summary = f"install complete: {len(report.written)} written, {len(report.current)} current"
        return CommandResult(
            success=True,
            output=summary,
            info=info,
            warnings=warnings,
            metadata={
                "written": report.written,
                "current": report.current,
                "displaced": [{"path": o, "backup": b} for o, b in report.displaced],
            },
        )


class CommandAssetsRefresh:
    """Re-install exactly the operators recorded in the manifest."""

    def execute(self) -> CommandResult:
        try:
            report = installer.refresh()
        except (UnknownOperatorError, ManifestError) as exc:
            return CommandResult(success=False, error=str(exc))

        if not report.written and not report.current:
            return CommandResult(success=True, output="nothing installed yet; nothing to refresh")

        info = [f"wrote: {p}" for p in report.written]
        info += [f"current: {p}" for p in report.current]
        warnings = [f"backed up your edit of {orig} to {backup}" for orig, backup in report.displaced]
        summary = f"refresh complete: {len(report.written)} written, {len(report.current)} current"
        return CommandResult(
            success=True,
            output=summary,
            info=info,
            warnings=warnings,
            metadata={
                "written": report.written,
                "current": report.current,
                "displaced": [{"path": o, "backup": b} for o, b in report.displaced],
            },
        )


class CommandAssetsStatus:
    """Report what is installed: per file, operator, path, recorded version, drift."""

    def execute(self) -> CommandResult:
        try:
            statuses = installer.status()
        except ManifestError as exc:
            return CommandResult(success=False, error=str(exc))

        if not statuses:
            return CommandResult(success=True, output="no assets installed")

        lines: list[str] = []
        for s in statuses:
            flags: list[str] = []
            if not s.present:
                flags.append("MISSING")
            elif not s.hash_matches:
                flags.append("edited (refresh will back it up)")
            if s.behind_cli:
                flags.append("behind CLI")
            suffix = f"  [{'; '.join(flags)}]" if flags else "  [current]"
            lines.append(f"{s.operator}: {s.path} (v{s.recorded_version}){suffix}")

        return CommandResult(
            success=True,
            output="\n".join(lines),
            metadata={
                "assets": [
                    {
                        "operator": s.operator,
                        "path": s.path,
                        "recorded_version": s.recorded_version,
                        "present": s.present,
                        "hash_matches": s.hash_matches,
                        "behind_cli": s.behind_cli,
                    }
                    for s in statuses
                ],
            },
        )


class CommandAssetsUninstall:
    """Remove klyreon's untouched files; keep edited ones and say so."""

    def __init__(self, operators: list[str]) -> None:
        self.operators = operators

    def execute(self) -> CommandResult:
        operators = self.operators or _default_operators()
        if not operators:
            return CommandResult(success=True, output="no assets installed; nothing to uninstall")
        try:
            report = installer.uninstall(operators)
        except (UnknownOperatorError, ManifestError) as exc:
            return CommandResult(success=False, error=str(exc))

        info = [f"removed: {p}" for p in report.removed]
        warnings = [f"kept {p}: {reason}" for p, reason in report.kept]
        summary = f"uninstall complete: {len(report.removed)} removed, {len(report.kept)} kept"
        return CommandResult(
            success=True,
            output=summary,
            info=info,
            warnings=warnings,
            metadata={
                "removed": report.removed,
                "kept": [{"path": p, "reason": r} for p, r in report.kept],
            },
        )

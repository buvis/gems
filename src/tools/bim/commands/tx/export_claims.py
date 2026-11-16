"""``bim tx export-claims``: emit the tiromex claim index as JSON."""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import TYPE_CHECKING

from buvis.pybase.filesystem import atomic_write_text
from buvis.pybase.result import CommandResult

from bim.commands.tx.shared.claims import collect_claims
from bim.commands.tx.shared.format import TxNote, read_note
from bim.commands.tx.shared.paths import iter_note_files, to_vault_rel

if TYPE_CHECKING:
    from pathlib import Path

    from bim.commands.tx.shared.paths import TiromexPaths

_SCHEMA_VERSION = 1


class CommandTxExportClaims:
    """Emit every claim of the tiromex concept notes as JSON.

    Claims on rejected notes are included. ``out`` is refused when it resolves
    under the vault root: the claim set is derived state.
    """

    def __init__(self, paths: TiromexPaths, *, out: Path | None = None, now: dt.datetime | None = None) -> None:
        self.paths = paths
        self.out = out
        self.now = now

    def execute(self) -> CommandResult:
        """Collect the claims and print them or write them to ``out``."""
        dest = None if self.out is None else self.out.expanduser().resolve()
        if dest is not None and any(
            path.exists() and os.path.samefile(path, self.paths.vault_root) for path in (dest, *dest.parents)
        ):
            return CommandResult(
                success=False,
                error=(
                    f"--out {self.out} resolves under the vault root {self.paths.vault_root}; refused. "
                    "The claim set is derived state and must live outside the vault."
                ),
            )

        notes: list[TxNote] = []
        warnings: list[str] = []
        for file in iter_note_files(self.paths):
            try:
                notes.append(read_note(self.paths, file))
            except (OSError, ValueError) as exc:
                warnings.append(f"skipped unparseable note {to_vault_rel(self.paths, file)}: {exc}")

        claims = collect_claims(notes)
        generated = (self.now or dt.datetime.now().astimezone()).isoformat()
        payload = {"schema_version": _SCHEMA_VERSION, "generated": generated, "claims": claims}
        text = json.dumps(payload, indent=2)
        metadata = {"claim_count": len(claims)}

        if dest is None:
            return CommandResult(success=True, output=text, warnings=warnings, metadata=metadata)

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(dest, text + "\n")
        except OSError as exc:
            return CommandResult(success=False, error=f"cannot write {dest}: {exc}", warnings=warnings)
        return CommandResult(
            success=True,
            output=f"wrote {len(claims)} claim(s) to {dest}",
            warnings=warnings,
            metadata=metadata,
        )

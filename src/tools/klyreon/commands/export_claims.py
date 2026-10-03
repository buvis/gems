"""``klyreon export-claims`` -- emit the claim index as JSON."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from buvis.pybase.filesystem import atomic_write_text
from buvis.pybase.result import CommandResult

from klyreon.spec.enums import Assent, Lifecycle
from klyreon.spec.model import FileKind
from klyreon.spec.parser import FrontmatterError, parse_file

_SCHEMA_VERSION = 1


class CommandExportClaims:
    """Emit every claim in the vault as JSON.

    Claims on ``assent: rejected`` zettels ARE included (discovery Q13) so a
    caller can tell a conflict with endorsed material from a conflict with
    material the vault already refused; each row carries its parent's ``assent``
    and ``lifecycle``. ``--out`` refuses any path resolving under the vault root:
    the claim set is derived state, and the vault holds only knowledge.
    """

    def __init__(self, root: Path, *, out: Path | None = None, now: dt.datetime | None = None) -> None:
        self.root = root
        self.out = out
        self.now = now

    def execute(self) -> CommandResult:
        if self.out is not None:
            refusal = self._reject_in_vault(self.out)
            if refusal is not None:
                return refusal

        notes_dir = self.root / "wiki" / "notes"
        claims: list[dict[str, object]] = []
        warnings: list[str] = []

        if notes_dir.is_dir():
            for md in sorted(notes_dir.rglob("*.md")):
                rel = md.relative_to(self.root).as_posix()
                try:
                    doc = parse_file(md, FileKind.ZETTEL)
                except (FrontmatterError, OSError) as exc:
                    warnings.append(f"skipped unparseable zettel {rel}: {exc}")
                    continue
                assent = doc.get("assent", Assent.UNKNOWN.value)
                lifecycle = doc.get("lifecycle", Lifecycle.FLEETING.value)
                for claim in doc.get("claims") or []:
                    if isinstance(claim, dict) and "id" in claim and "statement" in claim:
                        claims.append(
                            {
                                "zettel": rel,
                                "assent": assent,
                                "lifecycle": lifecycle,
                                "claim_id": claim["id"],
                                "statement": claim["statement"],
                            },
                        )

        generated = (self.now or dt.datetime.now().astimezone()).isoformat()
        payload = {"schema_version": _SCHEMA_VERSION, "generated": generated, "claims": claims}
        text = json.dumps(payload, indent=2, sort_keys=False)

        if self.out is not None:
            self.out.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(self.out, text + "\n")
            return CommandResult(
                success=True,
                output=f"wrote {len(claims)} claim(s) to {self.out}",
                warnings=warnings,
                metadata={"claim_count": len(claims)},
            )

        return CommandResult(success=True, output=text, warnings=warnings, metadata={"claim_count": len(claims)})

    def _reject_in_vault(self, out: Path) -> CommandResult | None:
        root_resolved = self.root.resolve()
        out_resolved = out.expanduser().resolve()
        if out_resolved == root_resolved or root_resolved in out_resolved.parents:
            return CommandResult(
                success=False,
                error=(
                    f"--out {out} resolves under the vault root {root_resolved}; refused. "
                    "The claim set is derived state and must live outside the vault."
                ),
            )
        return None

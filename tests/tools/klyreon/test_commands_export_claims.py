"""export-claims: JSON contract, 200-zettel scale, rejected labelling, write refusal."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from klyreon.commands.export_claims import CommandExportClaims
from klyreon.spec.model import Document, FileKind
from klyreon.spec.writer import write_document


def _make_vault(root: Path) -> None:
    for sub in ("sources", "wiki/notes", "wiki/mocs", "wiki/trails"):
        (root / sub).mkdir(parents=True)


def _write_zettel(root: Path, zid: str, *, assent: str, claims: list[dict[str, str]]) -> None:
    created = f"{zid[0:4]}-{zid[4:6]}-{zid[6:8]}T{zid[8:10]}:{zid[10:12]}:{zid[12:14]}+02:00"
    doc = Document(
        path=f"wiki/notes/{zid}.md",
        kind=FileKind.ZETTEL,
        frontmatter={
            "id": zid,
            "title": f"Z {zid}",
            "created": created,
            "type": "note",
            "concept-type": "observation",
            "assent": assent,
            "lifecycle": "fleeting",
            "claims": claims,
            "mocs": ["wiki/mocs/a.md"],
        },
        body=f"\n# Z {zid}\n",
        h1=f"Z {zid}",
    )
    write_document(doc, root / "wiki" / "notes" / f"{zid}.md")


class TestExportClaims:
    def test_200_zettel_schema(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        _make_vault(root)
        base = dt.datetime(2026, 1, 1, 0, 0, 0)
        for i in range(200):
            zid = (base + dt.timedelta(seconds=i)).strftime("%Y%m%d%H%M%S")
            _write_zettel(root, zid, assent="tentative", claims=[{"id": "c1", "statement": f"claim {i}"}])

        result = CommandExportClaims(root).execute()
        assert result.success
        payload = json.loads(result.output or "")
        assert payload["schema_version"] == 1
        assert "generated" in payload
        assert len(payload["claims"]) == 200
        sample = payload["claims"][0]
        assert set(sample) == {"zettel", "assent", "lifecycle", "claim_id", "statement"}
        assert sample["zettel"].startswith("wiki/notes/")

    def test_rejected_zettel_claim_present_and_labelled(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        _make_vault(root)
        _write_zettel(root, "20260101000000", assent="rejected", claims=[{"id": "c1", "statement": "refused claim"}])
        payload = json.loads(CommandExportClaims(root).execute().output or "")
        assert len(payload["claims"]) == 1
        assert payload["claims"][0]["assent"] == "rejected"
        assert payload["claims"][0]["statement"] == "refused claim"

    def test_out_under_vault_root_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        _make_vault(root)
        result = CommandExportClaims(root, out=root / "claims.json").execute()
        assert result.success is False
        assert "refused" in (result.error or "")

    def test_out_outside_vault_writes_file(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        _make_vault(root)
        _write_zettel(root, "20260101000000", assent="accepted", claims=[{"id": "c1", "statement": "s"}])
        out = tmp_path / "exports" / "claims.json"
        result = CommandExportClaims(root, out=out).execute()
        assert result.success is True
        assert out.is_file()
        assert json.loads(out.read_text())["claims"][0]["assent"] == "accepted"

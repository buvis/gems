"""Tests for ``collect_claims``, ``CommandTxValidate`` and ``CommandTxExportClaims``."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from bim.commands.tx.export_claims import CommandTxExportClaims
from bim.commands.tx.shared.claims import collect_claims
from bim.commands.tx.shared.format import TxNote, read_note
from bim.commands.tx.shared.paths import TiromexPaths, iter_note_files, resolve_tiromex
from bim.commands.tx.shared.validator import validate_tiromex
from bim.commands.tx.validate import CommandTxValidate

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.tools.bim.tx.conftest import TxNoteBuilder, TxVault

INDEX_ID = "20260411140000"
A_ID = "20260411145300"
B_ID = "20260412090000"
C_ID = "20260413100000"
D_ID = "20260414110000"
LONG_STATEMENT = (
    "Poznání vyžaduje důvody: knowledge needs reasons that the knower can state, "
    "check against the world and defend when another person asks for them"
)
TITLES = {
    A_ID: "Knowledge is justified belief",
    B_ID: "Belief needs grounds",
    C_ID: "Grounds need reasons",
}
ROW_KEYS = ["zettel", "assent", "lifecycle", "claim_id", "statement"]
PAYLOAD_KEYS = ["schema_version", "generated", "claims"]
NOW_A = datetime(2026, 11, 16, 9, 30, 5).astimezone()
NOW_B = datetime(2025, 1, 2, 23, 4, 0).astimezone()
NO_FRONT_MATTER = "no front matter here\n"


def _claims(*rows: tuple[str, str]) -> str:
    return "claims:\n" + "".join(f'  - id: {claim_id}\n    statement: "{text}"\n' for claim_id, text in rows)


def _concept(
    tx_notes: TxNoteBuilder,
    note_id: str,
    claims_yaml: str,
    *,
    assent: str | None = "tentative",
    lifecycle: str | None = "fleeting",
    folder: Path | None = None,
) -> Path:
    """Write a concept note whose assent, lifecycle and claims block are given verbatim."""
    text = tx_notes.concept(note_id, TITLES.get(note_id, "Outside thought"), claims=[])
    meta = (f"assent: {assent}\n" if assent else "") + (f"lifecycle: {lifecycle}\n" if lifecycle else "")
    text = text.replace("assent: tentative\nlifecycle: fleeting\n", meta + claims_yaml, 1)
    return tx_notes.write(text, note_id, folder)


def _with_meta(text: str, extra: str) -> str:
    return text.replace("processed: false\n", f"processed: false\n{extra}", 1)


def _row(
    stem: str,
    claim_id: str,
    statement: str,
    assent: str = "tentative",
    lifecycle: str = "fleeting",
) -> dict[str, str]:
    return {
        "zettel": f"notes/tiromex/{stem}.md",
        "assent": assent,
        "lifecycle": lifecycle,
        "claim_id": claim_id,
        "statement": statement,
    }


def _tree(base: Path) -> list[str]:
    return sorted(path.relative_to(base).as_posix() for path in base.rglob("*"))


def _alias(vault: TxVault, target: Path) -> Path:
    link = vault.root.parent / "alias"
    link.symlink_to(target, target_is_directory=True)
    return link


def _notes(paths: TiromexPaths) -> list[TxNote]:
    return [read_note(paths, file) for file in iter_note_files(paths)]


@pytest.fixture
def paths(tx_vault: TxVault) -> TiromexPaths:
    return resolve_tiromex(tx_vault.zettelkasten, "tiromex")


@pytest.fixture
def concept_rows(tx_notes: TxNoteBuilder) -> list[dict[str, str]]:
    """Write an index and four concept notes (one rejected, one in a subfolder); return their claim rows."""
    tx_notes.write(tx_notes.index(), INDEX_ID)
    _concept(tx_notes, A_ID, _claims(("c1", "Belief is not enough")))
    _concept(
        tx_notes,
        B_ID,
        _claims(("c2", "Grounds come first"), ("c1", "Grounds are reasons")),
        assent="rejected",
        lifecycle="evergreen",
    )
    _concept(tx_notes, C_ID, _claims(("c1", LONG_STATEMENT)))
    _concept(tx_notes, D_ID, _claims(("s1", "Nested notes count")), folder=tx_notes.vault.folder / "sub")
    return [
        _row(A_ID, "c1", "Belief is not enough"),
        _row(B_ID, "c2", "Grounds come first", "rejected", "evergreen"),
        _row(B_ID, "c1", "Grounds are reasons", "rejected", "evergreen"),
        _row(C_ID, "c1", LONG_STATEMENT),
        _row(f"sub/{D_ID}", "s1", "Nested notes count"),
    ]


class TestCollectClaims:
    def test_empty_input_gives_no_rows(self) -> None:
        assert collect_claims([]) == []

    def test_rows_in_note_path_order_then_claim_order(
        self, paths: TiromexPaths, concept_rows: list[dict[str, str]]
    ) -> None:
        rows = collect_claims(list(reversed(_notes(paths))))

        assert rows == concept_rows
        assert [list(row) for row in rows] == [ROW_KEYS] * 5

    def test_missing_assent_and_lifecycle_take_defaults(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, _claims(("c1", "No fields")), assent=None, lifecycle=None)
        _concept(tx_notes, B_ID, _claims(("c1", "Only lifecycle")), assent=None, lifecycle="literature")
        _concept(tx_notes, C_ID, _claims(("c1", "Only assent")), assent="accepted", lifecycle=None)

        assert collect_claims(_notes(paths)) == [
            _row(A_ID, "c1", "No fields", "unknown", "fleeting"),
            _row(B_ID, "c1", "Only lifecycle", "unknown", "literature"),
            _row(C_ID, "c1", "Only assent", "accepted", "fleeting"),
        ]

    def test_only_well_formed_claims_on_concept_notes(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        mixed = (
            _claims(("c1", "Kept first"))
            + '  - "a loose string"\n'
            + "  - id: c3\n"
            + '  - statement: "No id"\n'
            + "  - id: c6\n    statement:\n"
            + "  - id: c7\n    statement: null\n"
            + '  - id: c8\n    statement: ""\n'
            + '  - id:\n    statement: "Empty id"\n'
            + '  - id: null\n    statement: "Null id"\n'
            + '  - id: ""\n    statement: "Blank id"\n'
            + '  - id: c5\n    statement: "Kept last"\n'
        )
        _concept(tx_notes, A_ID, mixed)
        _concept(tx_notes, B_ID, 'claims: "not a list"\n')
        tx_notes.write(_with_meta(tx_notes.index(), _claims(("i1", "Index claim"))), INDEX_ID)
        tx_notes.write(_with_meta(tx_notes.run(), _claims(("r1", "Run claim"))), "20260411150000")
        tx_notes.write(_with_meta(tx_notes.plain(), _claims(("p1", "Plain claim"))), "20260411160000")

        assert collect_claims(_notes(paths)) == [
            _row(A_ID, "c1", "Kept first"),
            _row(A_ID, "c5", "Kept last"),
        ]

    def test_every_row_value_is_a_string(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        _concept(tx_notes, A_ID, "claims:\n  - id: 7\n    statement: 2026-04-11\n  - id: c2\n    statement: 42\n")

        rows = collect_claims(_notes(paths))

        assert rows == [_row(A_ID, "7", "2026-04-11"), _row(A_ID, "c2", "42")]
        assert all(isinstance(value, str) for row in rows for value in row.values())
        assert json.loads(json.dumps(rows)) == rows


class TestValidateJson:
    def test_clean_folder(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        tx_notes.write(tx_notes.index(), INDEX_ID)
        tx_notes.write(tx_notes.concept(), A_ID)

        result = CommandTxValidate(paths, as_json=True).execute()

        assert result.success is True
        assert result.output == json.dumps({"clean": True, "error_count": 0, "errors": []}, indent=2, sort_keys=True)
        assert result.metadata == {"error_count": 0}

    def test_errors_give_a_failed_result_with_every_diagnostic(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder
    ) -> None:
        tx_notes.write(tx_notes.concept(), A_ID)
        for n in range(11):
            tx_notes.write(NO_FRONT_MATTER, f"broken-{n:02d}")
        found = validate_tiromex(paths)
        errors = [{"path": d.path, "rule": d.rule, "message": d.message, "line": d.line} for d in found]

        result = CommandTxValidate(paths, as_json=True).execute()

        assert len(found) > 11
        assert {d.rule for d in found} >= {"dangling-moc", "parse-error"}
        assert result.success is False
        assert result.output == json.dumps(
            {"clean": False, "error_count": len(found), "errors": errors}, indent=2, sort_keys=True
        )
        payload = json.loads(result.output)
        assert len(payload["errors"]) == payload["error_count"] == len(found)
        assert all(set(error) == {"path", "rule", "message", "line"} for error in payload["errors"])
        assert result.metadata == {"error_count": len(found)}

    @pytest.mark.parametrize(("body_lines", "expected"), [(60, 0), (61, 1)])
    def test_default_body_limit_is_sixty_lines(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, body_lines: int, expected: int
    ) -> None:
        filler = "".join(f"Line {n} of the body.\n" for n in range(1, body_lines))
        tx_notes.write(tx_notes.index(), INDEX_ID)
        tx_notes.write(tx_notes.concept().replace("The claim holds for ordinary cases.\n", filler, 1), A_ID)

        def rules(**limit: int) -> list[str]:
            output = CommandTxValidate(paths, as_json=True, **limit).execute().output
            return [error["rule"] for error in json.loads(output)["errors"]]

        assert rules(max_body_lines=body_lines) == []
        assert rules(max_body_lines=body_lines - 1) == ["oversized-body"]
        assert rules() == ["oversized-body"] * expected

    @pytest.mark.parametrize(("max_body_lines", "expected"), [(1, 2), (2, 1), (60, 0)])
    def test_max_body_lines_reaches_the_validator(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, max_body_lines: int, expected: int
    ) -> None:
        tx_notes.write(tx_notes.index(), INDEX_ID)
        tx_notes.write(tx_notes.concept(), A_ID)

        result = CommandTxValidate(paths, as_json=True, max_body_lines=max_body_lines).execute()

        payload = json.loads(result.output)
        assert [error["rule"] for error in payload["errors"]] == ["oversized-body"] * expected
        assert payload["error_count"] == expected
        assert payload["clean"] is (expected == 0)
        assert result.success is (expected == 0)


class TestValidateText:
    @pytest.mark.parametrize("folder_name", ["tiromex", "atlas"])
    def test_clean_folder_names_the_folder(self, tx_vault: TxVault, tx_notes: TxNoteBuilder, folder_name: str) -> None:
        paths = resolve_tiromex(tx_vault.zettelkasten, folder_name)
        tx_notes.write(tx_notes.index(members=[]), INDEX_ID, paths.folder)

        result = CommandTxValidate(paths).execute()

        assert result.success is True
        assert result.output == f"tiromex is clean: {paths.folder}"
        assert result.error is None

    def test_empty_folder_is_clean(self, paths: TiromexPaths) -> None:
        result = CommandTxValidate(paths).execute()

        assert result.success is True
        assert result.output == f"tiromex is clean: {paths.folder}"

    @pytest.mark.parametrize("broken", [False, True])
    def test_dirty_folder_lists_each_error(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, broken: bool) -> None:
        tx_notes.write(tx_notes.concept(), A_ID)
        if broken:
            tx_notes.write(NO_FRONT_MATTER, "broken")
        found = validate_tiromex(paths)
        lines = [f"{d.path}: [{d.rule}] {d.message}" for d in found]

        result = CommandTxValidate(paths).execute()

        assert len(found) >= 1 + broken
        assert result.success is False
        assert result.error == f"{len(found)} validation error(s):\n" + "\n".join(lines)


class TestExportClaimsPayload:
    @pytest.mark.parametrize("now", [NOW_A, NOW_B])
    def test_exact_payload_and_row_keys(
        self, paths: TiromexPaths, concept_rows: list[dict[str, str]], now: datetime
    ) -> None:
        result = CommandTxExportClaims(paths, now=now).execute()

        payload = json.loads(result.output)
        assert result.success is True
        assert list(payload) == PAYLOAD_KEYS
        assert payload["schema_version"] == 1
        assert payload["generated"] == now.isoformat()
        assert payload["claims"] == concept_rows
        assert [list(row) for row in payload["claims"]] == [ROW_KEYS] * 5
        assert result.output == json.dumps(payload, indent=2)
        assert result.metadata == {"claim_count": 5}
        assert result.warnings == []

    def test_generated_defaults_to_local_now(self, paths: TiromexPaths) -> None:
        before = datetime.now().astimezone()
        result = CommandTxExportClaims(paths).execute()
        after = datetime.now().astimezone()

        generated = datetime.fromisoformat(json.loads(result.output)["generated"])
        assert generated.utcoffset() == before.utcoffset()
        assert before - timedelta(seconds=1) <= generated <= after

    def test_empty_folder_exports_no_claims(self, paths: TiromexPaths) -> None:
        result = CommandTxExportClaims(paths, now=NOW_A).execute()

        assert json.loads(result.output) == {"schema_version": 1, "generated": NOW_A.isoformat(), "claims": []}
        assert result.metadata == {"claim_count": 0}

    def test_rejected_claims_stay_and_plain_and_outside_claims_do_not(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, tx_vault: TxVault
    ) -> None:
        _concept(tx_notes, A_ID, _claims(("c1", "Rejected but kept")), assent="rejected")
        tx_notes.write(_with_meta(tx_notes.plain(), _claims(("p1", "Plain claim"))), "20260411160000")
        _concept(tx_notes, B_ID, _claims(("o1", "Outside claim")), folder=tx_vault.zettelkasten / "other")
        _concept(tx_notes, C_ID, _claims(("o2", "Root claim")), folder=tx_vault.root)
        near = tx_vault.zettelkasten / "tiromex-old"
        _concept(tx_notes, "20260414110000", _claims(("o3", "Near claim")), folder=near)

        result = CommandTxExportClaims(paths, now=NOW_A).execute()

        assert json.loads(result.output)["claims"] == [_row(A_ID, "c1", "Rejected but kept", "rejected")]
        assert result.metadata == {"claim_count": 1}
        for absent in ("Plain claim", "Outside claim", "Root claim", "Near claim"):
            assert absent not in result.output

    def test_unparseable_notes_become_warnings_not_payload_keys(
        self, paths: TiromexPaths, concept_rows: list[dict[str, str]], tx_notes: TxNoteBuilder
    ) -> None:
        tx_notes.write(NO_FRONT_MATTER, "broken")
        tx_notes.write(NO_FRONT_MATTER, "zz-broken")

        result = CommandTxExportClaims(paths, now=NOW_B).execute()

        payload = json.loads(result.output)
        assert result.success is True
        assert list(payload) == PAYLOAD_KEYS
        assert payload["claims"] == concept_rows
        assert result.metadata == {"claim_count": 5}
        assert len(result.warnings) == 2
        assert all(warning.startswith("skipped unparseable note ") for warning in result.warnings)
        for stem in ("broken", "zz-broken"):
            marker = f"notes/tiromex/{stem}.md: "
            [warning] = [warning for warning in result.warnings if marker in warning]
            assert warning.split(marker, 1)[1].strip()
        assert "skipped" not in result.output


REFUSED_OUTS = [
    lambda vault: vault.root,
    lambda vault: vault.root / "claims.json",
    lambda vault: vault.folder / "claims.json",
    lambda vault: vault.root / "new" / "dir" / "claims.json",
    lambda vault: vault.folder / ".." / ".." / "claims.json",
    lambda vault: _alias(vault, vault.root) / "claims.json",
    lambda vault: _alias(vault, vault.folder) / "deep" / "claims.json",
]
REFUSED_IDS = ["root", "under-root", "in-folder", "new-dirs", "dotdot", "alias-root", "alias-folder"]


class TestExportClaimsOut:
    def test_writes_the_payload_outside_the_vault(
        self, paths: TiromexPaths, concept_rows: list[dict[str, str]], tx_vault: TxVault
    ) -> None:
        out = tx_vault.root.parent / "exports" / "2026" / "claims.json"
        out.parent.mkdir(parents=True)
        out.write_text('{"stale": "junk"}\n', encoding="utf-8")
        expected = {"schema_version": 1, "generated": NOW_A.isoformat(), "claims": concept_rows}

        result = CommandTxExportClaims(paths, out=out, now=NOW_A).execute()

        assert result.success is True
        assert result.output == f"wrote 5 claim(s) to {out}"
        assert result.metadata == {"claim_count": 5}
        assert out.read_text(encoding="utf-8") == json.dumps(expected, indent=2) + "\n"

    @pytest.mark.parametrize("make_out", REFUSED_OUTS, ids=REFUSED_IDS)
    def test_refuses_a_destination_under_the_vault_root(
        self,
        paths: TiromexPaths,
        tx_vault: TxVault,
        tx_notes: TxNoteBuilder,
        make_out: Callable[[TxVault], Path],
    ) -> None:
        _concept(tx_notes, A_ID, _claims(("c1", "Kept")))
        out = make_out(tx_vault)
        before = _tree(tx_vault.root.parent)

        result = CommandTxExportClaims(paths, out=out, now=NOW_A).execute()

        assert result.success is False
        assert result.error.startswith(f"--out {out} resolves under the vault root")
        assert _tree(tx_vault.root.parent) == before

    @pytest.mark.parametrize("name", ["vault-exports/claims.json", "vaultclaims.json"])
    def test_sibling_sharing_the_vault_prefix_is_accepted(
        self, paths: TiromexPaths, tx_vault: TxVault, name: str
    ) -> None:
        out = tx_vault.root.parent / name

        result = CommandTxExportClaims(paths, out=out, now=NOW_A).execute()

        assert result.success is True
        assert json.loads(out.read_text(encoding="utf-8"))["claims"] == []

    def test_relative_out_resolves_against_the_working_directory(
        self, paths: TiromexPaths, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        elsewhere = tx_vault.root.parent / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(tx_vault.folder)
        refused = CommandTxExportClaims(paths, out=Path("claims.json"), now=NOW_A).execute()
        monkeypatch.chdir(elsewhere)
        written = CommandTxExportClaims(paths, out=Path("claims.json"), now=NOW_A).execute()

        assert refused.success is False
        assert refused.error.startswith("--out claims.json resolves under the vault root")
        assert not (tx_vault.folder / "claims.json").exists()
        assert written.success is True
        assert written.output == f"wrote 0 claim(s) to {elsewhere / 'claims.json'}"
        assert (elsewhere / "claims.json").is_file()

    def test_tilde_out_writes_to_home_from_inside_the_vault(
        self, paths: TiromexPaths, tx_vault: TxVault, tx_notes: TxNoteBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _concept(tx_notes, A_ID, _claims(("c1", "Kept")))
        monkeypatch.chdir(tx_vault.folder)
        before = _tree(tx_vault.root)

        result = CommandTxExportClaims(paths, out=Path("~/x.json"), now=NOW_A).execute()

        dest = tx_vault.home / "x.json"
        assert result.success is True
        assert result.output == f"wrote 1 claim(s) to {dest}"
        assert json.loads(dest.read_text(encoding="utf-8"))["claims"] == [_row(A_ID, "c1", "Kept")]
        assert _tree(tx_vault.root) == before

    def test_tilde_out_is_refused_when_home_is_inside_the_vault(
        self, paths: TiromexPaths, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        inside_home = tx_vault.root / "home"
        inside_home.mkdir()
        monkeypatch.setenv("HOME", str(inside_home))
        monkeypatch.chdir(tx_vault.root.parent)

        result = CommandTxExportClaims(paths, out=Path("~/x.json"), now=NOW_A).execute()

        assert result.success is False
        assert result.error.startswith("--out ~/x.json resolves under the vault root")
        assert not (inside_home / "x.json").exists()

    def test_unwritable_destination_gives_a_failed_result(self, paths: TiromexPaths, tx_vault: TxVault) -> None:
        blocker = tx_vault.root.parent / "afile"
        blocker.write_text("not a directory\n", encoding="utf-8")

        result = CommandTxExportClaims(paths, out=blocker / "claims.json", now=NOW_A).execute()

        assert result.success is False
        assert result.error
        assert "resolves under the vault root" not in result.error
        assert blocker.read_text(encoding="utf-8") == "not a directory\n"

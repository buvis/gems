"""CLI integration tests for the ``bim tx`` group (PRD 00150 task 7).

Every test runs the real ``bim`` Click group through ``CliRunner`` against a
scratch vault under ``tmp_path`` (see ``conftest.py``).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import pytest
import tomllib
from bim.cli import SKILL_PATH, cli
from click.testing import CliRunner, Result

if TYPE_CHECKING:
    from tests.tools.bim.tx.conftest import TxNoteBuilder, TxVault

MANIFEST_PATH = SKILL_PATH.with_name("manifest.toml")

APPROVAL_RULE = (
    "The notes are private. Their content (notes, inbox, daily notes, archives,\n"
    "tags, titles, query and search results) must not reach your session without\n"
    "the user's explicit approval. Read only what the user asked you to read, and\n"
    "only that. Ask before any other read: tag lookups, duplicate checks, parent\n"
    "notes, the vault's own docs, or background context. Creating a note needs no\n"
    "approval; the `--json` report holds only paths and metadata."
)

NEVER = "maintenance has never run"
UNREADABLE = "maintenance state is unreadable"
STALE_DAYS = 12
FRESH_DAYS = 3
STALE = f"maintenance is stale: last run {STALE_DAYS}d ago"

ZETTEL_TYPES = ["note", "definition", "procedure", "cheatsheet", "snippet", "course", "ai-prompt"]
CONCEPT_TYPES = ["thesis", "argument", "aporia", "question", "example", "observation"]
STATUS_PREFIXES = [
    "tiromex:",
    "notes:",
    "lifecycle:",
    "assent:",
    "mean links/note:",
    "aporia notes:",
    "prune candidates:",
    "git:",
    "maintenance:",
]
CLAIM_KEYS = ["zettel", "assent", "lifecycle", "claim_id", "statement"]


def _invoke(*args: str) -> Result:
    return CliRunner().invoke(cli, list(args), catch_exceptions=False)


def _flat(text: str) -> str:
    """Drop all whitespace, so Rich line wrapping cannot hide a match."""
    return "".join(text.split())


def _write_state(vault: TxVault, content: str) -> None:
    state_file = vault.state_home / "bim" / "tx" / "state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(content, encoding="utf-8")


def _stamp(days_ago: int) -> str:
    when = dt.datetime.now().astimezone() - dt.timedelta(days=days_ago)
    return json.dumps({"last_maintain": when.isoformat()})


def _set_state(vault: TxVault, state: str) -> None:
    if state == "unparseable":
        _write_state(vault, '{"last_maintain": "not a date"}')
    elif state == "stale":
        _write_state(vault, _stamp(STALE_DAYS))
    elif state == "fresh":
        _write_state(vault, _stamp(FRESH_DAYS))


def _long_statement(word: str) -> str:
    text = " ".join([word] * 60)
    return (text + " end" * 100)[:300]


def _write_unparseable(vault: TxVault, stem: str = "bad") -> Path:
    path = vault.folder / "[draft]" / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("no front matter here\n", encoding="utf-8")
    return path


def _md_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.md"))


def _assert_payload_header(payload: dict[str, object]) -> None:
    assert list(payload) == ["schema_version", "generated", "claims"]
    assert payload["schema_version"] == 1
    generated = dt.datetime.fromisoformat(str(payload["generated"]))
    assert generated.tzinfo is not None
    assert abs(dt.datetime.now().astimezone() - generated) < dt.timedelta(minutes=5)


def _without_generated(text: str) -> str:
    stamp = json.loads(text)["generated"]
    return text.replace(stamp, "<generated>")


class TestTxHelpIntegration:
    def test_integration_bim_and_tx_help_list_the_group_and_its_four_commands(self) -> None:
        top = _invoke("--help")
        group = _invoke("tx", "--help")

        assert top.exit_code == 0
        assert "tx" in top.stdout.split()
        assert group.exit_code == 0
        listed = [line.split()[0] for line in group.stdout.splitlines() if line.startswith("  ") and line.split()]
        for name in ("new", "validate", "export-claims", "status"):
            assert name in listed

    @pytest.mark.parametrize(
        ("command", "options", "absent"),
        [
            ("new", ["--title", "--type", "--concept-type"], ["--json", "--out"]),
            ("validate", ["--json"], ["--out", "--title"]),
            ("export-claims", ["--out"], ["--json", "--title"]),
            ("status", [], ["--json", "--out", "--title"]),
        ],
    )
    def test_integration_each_command_help_shows_its_own_options(
        self, command: str, options: list[str], absent: list[str]
    ) -> None:
        result = _invoke("tx", command, "--help")

        assert result.exit_code == 0
        for option in options:
            assert option in result.stdout
        for option in absent:
            assert option not in result.stdout


class TestTxNewIntegration:
    @pytest.mark.parametrize(
        ("args", "zettel_type", "concept_type"),
        [
            ([], "note", None),
            (["--type", "definition", "--concept-type", "argument"], "definition", "argument"),
            *[(["--type", value], value, None) for value in ZETTEL_TYPES],
            *[(["--concept-type", value], "note", value) for value in CONCEPT_TYPES],
        ],
    )
    def test_integration_new_prints_only_the_created_path(
        self, tx_vault: TxVault, args: list[str], zettel_type: str, concept_type: str | None
    ) -> None:
        result = _invoke("tx", "new", "--title", "Belief needs grounds", *args)

        assert result.exit_code == 0
        assert len(result.stdout.splitlines()) == 1
        created = Path(result.stdout.strip())
        assert created.is_file()
        assert created.parent == tx_vault.folder
        text = created.read_text(encoding="utf-8")
        assert f"\ntype: {zettel_type}\n" in text
        if concept_type is None:
            assert "concept-type:" not in text
        else:
            assert f"\nconcept-type: {concept_type}\n" in text

    def test_integration_new_follows_the_tiromex_folder_setting(
        self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tx_vault.zettelkasten / "atlas").mkdir()
        monkeypatch.setenv("BUVIS_BIM_TIROMEX_FOLDER", "atlas")

        result = _invoke("tx", "new", "--title", "Placed elsewhere")

        assert result.exit_code == 0
        assert Path(result.stdout.strip()).parent == tx_vault.zettelkasten / "atlas"
        assert _md_files(tx_vault.folder) == []

    @pytest.mark.parametrize(
        ("title", "present", "absent"),
        [
            ("", ["[required-field]", "[h1-exactly-one]"], []),
            ("line\n# two", ["[h1-exactly-one]"], ["[required-field]"]),
        ],
    )
    def test_integration_new_refusal_keeps_rule_ids_and_exits_1(
        self, tx_vault: TxVault, title: str, present: list[str], absent: list[str]
    ) -> None:
        result = _invoke("tx", "new", "--title", title, "--concept-type", "thesis")

        assert result.exit_code == 1
        output = _flat(result.output)
        assert _flat("refusing to write an invalid note") in output
        for rule in present:
            assert rule in output
        for rule in absent:
            assert rule not in output
        assert _md_files(tx_vault.folder) == []

    @pytest.mark.parametrize(
        ("args", "diagnostic"),
        [
            (["--type", "bogus"], "Invalid value for '--type'"),
            (["--type", "wiki-article"], "Invalid value for '--type'"),
            (["--concept-type", "theses"], "Invalid value for '--concept-type'"),
            ([], "Missing option '--title'"),
        ],
    )
    def test_integration_new_rejects_bad_choices_and_missing_title(
        self, tx_vault: TxVault, args: list[str], diagnostic: str
    ) -> None:
        title = [] if not args else ["--title", "Never written"]

        result = _invoke("tx", "new", *title, *args)

        assert result.exit_code == 2
        assert _flat(diagnostic) in _flat(result.output)
        assert _md_files(tx_vault.folder) == []


class TestTxValidateIntegration:
    def test_integration_validate_text_reports_errors_with_rule_ids(self, tx_notes: TxNoteBuilder) -> None:
        tx_notes.write(tx_notes.plain(), "20260411160000")
        bad = tx_notes.plain("20260411170000", "Todo").replace('title: "Todo"', 'title: ""')
        tx_notes.write(bad, "20260411170000")

        result = _invoke("tx", "validate")

        assert result.exit_code == 1
        output = _flat(result.output)
        header = re.search(r"(\d+)validationerror\(s\):", output)
        assert header is not None
        assert int(header.group(1)) == output.count(".md:[") >= 1
        located = _flat("notes/tiromex/20260411170000.md: [required-field]")
        assert located in output
        message = output.split(located, 1)[1].split("notes/tiromex/", 1)[0]
        assert re.search(r"[A-Za-z]{3}", message)
        assert "notes/tiromex/20260411160000.md" not in output

    @pytest.mark.parametrize("stems", [[], ["20260411160000", "20260411170000"]])
    def test_integration_validate_text_clean_folder_exits_0(self, tx_notes: TxNoteBuilder, stems: list[str]) -> None:
        for stem in stems:
            tx_notes.write(tx_notes.plain(stem, f"Note {stem}"), stem)

        result = _invoke("tx", "validate")

        assert result.exit_code == 0
        assert "tiromexisclean" in _flat(result.output)

    @pytest.mark.parametrize("stems", [[], ["20260411160000", "20260411170000"]])
    def test_integration_validate_json_clean_decodes_and_exits_0(
        self, tx_notes: TxNoteBuilder, stems: list[str]
    ) -> None:
        for stem in stems:
            tx_notes.write(tx_notes.plain(stem, f"Note {stem}"), stem)

        result = _invoke("tx", "validate", "--json")

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["clean"] is True
        assert payload["error_count"] == 0
        assert payload["errors"] == []

    def test_integration_validate_json_with_errors_exits_1_and_stdout_still_decodes(
        self, tx_vault: TxVault, tx_notes: TxNoteBuilder
    ) -> None:
        long_stem = "unparseable-" + "x" * 150
        _write_unparseable(tx_vault, long_stem)
        bad = tx_notes.plain("20260411170000", "Todo").replace('title: "Todo"', 'title: ""')
        tx_notes.write(bad, "20260411170000")

        result = _invoke("tx", "validate", "--json")

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["clean"] is False
        for error in payload["errors"]:
            assert set(error) == {"path", "rule", "message", "line"}
            assert isinstance(error["message"], str)
            assert error["message"].strip()
        paths = {error["path"] for error in payload["errors"]}
        assert f"notes/tiromex/[draft]/{long_stem}.md" in paths
        rules = {error["rule"] for error in payload["errors"] if error["path"] == "notes/tiromex/20260411170000.md"}
        assert "required-field" in rules
        assert payload["error_count"] == len(payload["errors"]) >= 2
        assert NEVER in " ".join(result.stderr.split())
        assert "maintenance" not in result.stdout


class TestTxExportClaimsIntegration:
    def test_integration_export_claims_stdout_is_whole_json_with_300_char_claims(
        self, tx_vault: TxVault, tx_notes: TxNoteBuilder
    ) -> None:
        first, second = _long_statement("knowledge"), _long_statement("belief")
        assert len(first) == len(second) == 300
        tx_notes.write(tx_notes.concept(claims=[("c1", first)]), "20260411145300")
        grounds = tx_notes.concept("20260412090000", "Belief needs grounds", claims=[("c1", second)])
        tx_notes.write(grounds, "20260412090000")
        _write_unparseable(tx_vault)

        result = _invoke("tx", "export-claims")

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        _assert_payload_header(payload)
        assert [list(claim) for claim in payload["claims"]] == [CLAIM_KEYS, CLAIM_KEYS]
        assert [(c["zettel"], c["claim_id"], c["statement"]) for c in payload["claims"]] == [
            ("notes/tiromex/20260411145300.md", "c1", first),
            ("notes/tiromex/20260412090000.md", "c1", second),
        ]
        assert _flat("skipped unparseable note notes/tiromex/[draft]/bad.md") in _flat(result.stderr)
        assert "unparseable" not in result.stdout

    def test_integration_export_claims_empty_folder_gives_empty_claim_list(self) -> None:
        result = _invoke("tx", "export-claims")

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        _assert_payload_header(payload)
        assert payload["claims"] == []

    @pytest.mark.parametrize("stems", [["20260411145300"], ["20260411145300", "20260412090000"]])
    def test_integration_export_claims_out_writes_file_and_reports_count(
        self, tx_notes: TxNoteBuilder, tmp_path: Path, stems: list[str]
    ) -> None:
        for stem in stems:
            tx_notes.write(tx_notes.concept(stem, f"Claim of {stem}"), stem)
        dest = (tmp_path / "exports" / "claims.json").resolve()

        result = _invoke("tx", "export-claims", "--out", str(dest))

        assert result.exit_code == 0
        assert result.stdout.strip() == f"wrote {len(stems)} claim(s) to {dest}"
        assert len(json.loads(dest.read_text(encoding="utf-8"))["claims"]) == len(stems)

    @pytest.mark.parametrize("rel", ["claims.json", "notes/exports/claims.json"])
    def test_integration_export_claims_out_inside_vault_fails_on_stderr(
        self, tx_vault: TxVault, tx_notes: TxNoteBuilder, rel: str
    ) -> None:
        tx_notes.write(tx_notes.concept(), "20260411145300")
        dest = tx_vault.root / rel

        result = _invoke("tx", "export-claims", "--out", str(dest))

        assert result.exit_code == 1
        assert result.stdout == ""
        assert "refused" in _flat(result.stderr)
        assert not dest.exists()

    @pytest.mark.parametrize(
        "rel", ["shelf/claims.json", "shelf/notes/tiromex/../../claims.json", "library/notes/../claims.json"]
    )
    def test_integration_export_claims_out_refuses_vault_reached_by_alias_or_dotdot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rel: str
    ) -> None:
        library = tmp_path.resolve() / "library"
        (library / "notes" / "tiromex").mkdir(parents=True)
        (tmp_path / "shelf").symlink_to(library, target_is_directory=True)
        monkeypatch.setenv("BUVIS_BIM_PATH_ZETTELKASTEN", str(library / "notes"))

        result = _invoke("tx", "export-claims", "--out", str(tmp_path / rel))

        assert result.exit_code == 1
        assert result.stdout == ""
        assert _flat("resolves under the vault root") in _flat(result.stderr)
        assert not (library / "claims.json").exists()

    def test_integration_export_claims_out_outside_vault_in_a_folder_named_vault_is_written(
        self, tx_notes: TxNoteBuilder, tmp_path: Path
    ) -> None:
        tx_notes.write(tx_notes.concept(claims=[("c1", _long_statement("grounds"))]), "20260411145300")
        dest = tmp_path.resolve() / "outside" / "vault" / "claims.json"

        written = _invoke("tx", "export-claims", "--out", str(dest))
        printed = _invoke("tx", "export-claims")

        assert written.exit_code == 0
        assert written.stdout.strip() == f"wrote 1 claim(s) to {dest}"
        text = dest.read_text(encoding="utf-8")
        assert text.endswith("}\n")
        assert _without_generated(text) == _without_generated(printed.stdout)
        _assert_payload_header(json.loads(text))


class TestTxStatusIntegration:
    def test_integration_status_prints_dashboard_on_stdout_and_warnings_on_stderr(
        self, tx_vault: TxVault, tx_notes: TxNoteBuilder
    ) -> None:
        tx_notes.write(tx_notes.concept(), "20260411145300")
        _write_unparseable(tx_vault)

        result = _invoke("tx", "status")

        assert result.exit_code == 0
        lines = result.stdout.splitlines()
        assert len(lines) == len(STATUS_PREFIXES)
        for line, prefix in zip(lines, STATUS_PREFIXES, strict=True):
            assert line.startswith(prefix)
        assert lines[0] == f"tiromex: {tx_vault.folder}"
        assert lines[1].startswith("notes: 1 (concept: 1")
        assert lines[2] == "lifecycle: fleeting=1"
        assert lines[3] == "assent: tentative=1"
        assert lines[8] == "maintenance: never run (stale)"
        assert _flat("skipped unparseable note notes/tiromex/[draft]/bad.md") in _flat(result.stderr)
        assert "unparseable" not in result.stdout


class TestStalenessIntegration:
    @pytest.mark.parametrize(("state", "wording"), [("never", NEVER), ("unparseable", UNREADABLE), ("stale", STALE)])
    @pytest.mark.parametrize(
        "args", [["new", "--title", "Fresh thought"], ["validate"], ["validate", "--json"], ["export-claims"]]
    )
    def test_integration_one_staleness_warning_on_stderr(
        self, tx_vault: TxVault, state: str, wording: str, args: list[str]
    ) -> None:
        _set_state(tx_vault, state)

        result = _invoke("tx", *args)

        stderr = " ".join(result.stderr.split())
        assert wording in stderr
        assert stderr.count("maintenance") == 1
        assert "maintenance" not in result.stdout

    @pytest.mark.parametrize("args", [["new", "--title", "Fresh thought"], ["validate"], ["export-claims"]])
    def test_integration_fresh_maintenance_gives_no_warning(self, tx_vault: TxVault, args: list[str]) -> None:
        _set_state(tx_vault, "fresh")

        result = _invoke("tx", *args)

        assert result.exit_code == 0
        assert "maintenance" not in result.output

    @pytest.mark.parametrize("days", [8, 30])
    def test_integration_stale_warning_names_the_real_day_count(self, tx_vault: TxVault, days: int) -> None:
        _write_state(tx_vault, _stamp(days))

        result = _invoke("tx", "validate")

        stderr = " ".join(result.stderr.split())
        assert f"maintenance is stale: last run {days}d ago" in stderr
        assert stderr.count("maintenance") == 1

    @pytest.mark.parametrize(("window", "days", "warns"), [("20", 12, False), ("5", 6, True)])
    def test_integration_staleness_window_follows_the_setting(
        self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch, window: str, days: int, warns: bool
    ) -> None:
        monkeypatch.setenv("BUVIS_BIM_TX__MAINTENANCE_WINDOW_DAYS", window)
        _write_state(tx_vault, _stamp(days))

        result = _invoke("tx", "validate")

        assert result.exit_code == 0
        stale = f"maintenance is stale: last run {days}d ago"
        assert (stale in " ".join(result.stderr.split())) is warns
        assert ("maintenance" in result.output) is warns

    @pytest.mark.parametrize(
        ("state", "line_start"),
        [
            ("never", "maintenance: never run (stale)"),
            ("unparseable", "maintenance: last_maintain unparseable (stale)"),
            ("stale", f"maintenance: last run {STALE_DAYS}d ago (stale, window 7d)"),
            ("fresh", f"maintenance: last run {FRESH_DAYS}d ago (fresh)"),
        ],
    )
    def test_integration_status_carries_one_staleness_line_in_stdout(
        self, tx_vault: TxVault, state: str, line_start: str
    ) -> None:
        _set_state(tx_vault, state)

        result = _invoke("tx", "status")

        assert result.exit_code == 0
        lines = [line for line in result.stdout.splitlines() if "maintenance" in line]
        assert len(lines) == 1
        assert lines[0].startswith(line_start)
        assert "maintenance" not in result.stderr

    def test_integration_other_bim_commands_do_not_warn(self, tx_notes: TxNoteBuilder) -> None:
        note = tx_notes.write(tx_notes.concept(), "20260411145300")

        result = _invoke("show", str(note))

        assert result.exit_code == 0
        assert "Knowledge is justified belief" in result.output
        assert "maintenance" not in result.output

    @pytest.mark.parametrize("state", ["never", "unparseable", "stale"])
    @pytest.mark.parametrize(
        ("command", "option"), [("new", "--title"), ("validate", "--json"), ("export-claims", "--out")]
    )
    def test_integration_help_prints_usage_and_no_staleness_warning(
        self, tx_vault: TxVault, state: str, command: str, option: str
    ) -> None:
        _set_state(tx_vault, state)

        result = _invoke("tx", command, "--help")

        assert result.exit_code == 0
        assert "Usage:" in result.stdout
        assert option in result.stdout
        assert "maintenance" not in result.stdout
        assert "maintenance" not in result.stderr


class TestTxImportWeightIntegration:
    def test_integration_importing_tx_cli_loads_no_zettel_infrastructure_module(self) -> None:
        code = (
            "import sys, bim.tx_cli; print('\\n'.join(sorted(n for n in sys.modules if 'zettel.infrastructure' in n)))"
        )

        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == ""

    def test_integration_the_zettel_infrastructure_probe_detects_a_heavy_import(self) -> None:
        code = (
            "import sys, buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter; "
            "print(any('zettel.infrastructure' in n for n in sys.modules))"
        )

        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)

        assert result.stdout.strip() == "True"


class TestTxNewTypeChoicesIntegration:
    def test_integration_new_type_option_offers_exactly_the_note_types_and_never_wiki_article(self) -> None:
        tx_group = cli.commands["tx"]
        assert isinstance(tx_group, click.Group)
        new = tx_group.commands["new"]
        type_option = next(param for param in new.params if "--type" in param.opts)

        assert isinstance(type_option.type, click.Choice)
        assert list(type_option.type.choices) == ZETTEL_TYPES
        assert "wiki-article" not in type_option.type.choices


class TestTiromexPathsErrorIntegration:
    @pytest.mark.parametrize("command", [["validate"], ["export-claims"], ["status"], ["new", "--title", "Lost"]])
    def test_integration_bad_folder_setting_panics_and_exits_1(
        self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch, command: list[str]
    ) -> None:
        monkeypatch.setenv("BUVIS_BIM_TIROMEX_FOLDER", "../tiromex")

        result = _invoke("tx", *command)

        assert result.exit_code == 1
        assert _flat("must be a single folder name") in _flat(result.output)
        assert _md_files(tx_vault.root) == []

    def test_integration_missing_zettelkasten_panic_prints_bracketed_path_whole(
        self, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tx_vault.root / "[draft]" / "absent"
        monkeypatch.setenv("BUVIS_BIM_PATH_ZETTELKASTEN", str(missing))

        result = _invoke("tx", "validate")

        assert result.exit_code == 1
        assert _flat(f"zettelkasten is not a directory: {missing}") in _flat(result.output)


def _create_note(title: str) -> Path:
    return Path(_invoke("tx", "new", "--title", title, "--concept-type", "thesis").stdout.strip())


class TestNewNoteVisibilityIntegration:
    def test_integration_new_note_is_visible_to_query_and_show(self, tx_vault: TxVault) -> None:
        from bim.commands.query.query import CommandQuery
        from bim.commands.show_note.show_note import CommandShowNote
        from bim.dependencies import get_evaluator, get_formatter, get_repo
        from bim.params.query import QueryParams
        from bim.params.show_note import ShowNoteParams
        from buvis.pybase.zettel.domain.value_objects.query_spec import QueryColumn, QuerySource, QuerySpec

        created = {title: _create_note(title) for title in ("Belief needs grounds", "Knowledge is justified belief")}
        directory = str(tx_vault.zettelkasten)
        columns = [QueryColumn(field="title"), QueryColumn(field="id")]
        spec = QuerySpec(source=QuerySource(directory=directory), columns=columns)

        query = CommandQuery(
            params=QueryParams(spec=spec, default_directory=directory), repo=get_repo(), evaluator=get_evaluator()
        ).execute()

        rows = {(row["title"], str(row["id"])) for row in query.metadata["rows"]}
        assert rows == {(title, path.stem) for title, path in created.items()}
        for title, path in created.items():
            params = ShowNoteParams(paths=[path])
            shown = CommandShowNote(params=params, repo=get_repo(), formatter=get_formatter()).execute()
            assert shown.success is True
            assert f"# {title}" in shown.output
            assert path.stem in shown.output


class TestShippedDocsIntegration:
    def test_integration_skill_keeps_approval_rule_then_tiromex_exception(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")

        assert text.count(APPROVAL_RULE) == 1
        after = text.split(APPROVAL_RULE + "\n\n", 1)[1]
        exception = after.split("\n\n", 1)[0]
        assert not exception.startswith("#")
        assert "<path_zettelkasten>/<tiromex_folder>/" in exception
        assert "notes/tiromex/" in exception
        assert "may read and write without asking" in " ".join(exception.split())
        assert "never" not in exception.lower()

    def test_integration_skill_has_tiromex_section_with_the_four_commands(self) -> None:
        text = SKILL_PATH.read_text(encoding="utf-8")

        assert text.count("\n## Tiromex\n") == 1
        section = text.split("\n## Tiromex\n", 1)[1].split("\n## ", 1)[0]
        assert len(section.strip().splitlines()) >= 20
        for usage in ("bim tx new --title", "bim tx validate", "bim tx export-claims", "bim tx status"):
            assert usage in section
        for term in ("concept-type", "assent", "lifecycle", "claims", "doubts", "supports"):
            assert term in section
        for shape in ("aporia", "refine", "supersede"):
            assert shape in section

    def test_integration_bim_skill_flag_prints_the_shipped_skill(self) -> None:
        result = _invoke("--skill")

        assert result.exit_code == 0
        assert result.stdout == SKILL_PATH.read_text(encoding="utf-8")
        assert "## Tiromex" in result.stdout

    def test_integration_manifest_lists_the_tx_commands(self) -> None:
        commands = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["tool"]["commands"]

        keys = ("tx_new", "tx_validate", "tx_export_claims", "tx_status")
        for key in keys:
            assert isinstance(commands.get(key), str)
            assert len(commands[key].split()) >= 3
        assert len({commands[key].strip().lower() for key in keys}) == len(keys)
        assert "create_note" in commands

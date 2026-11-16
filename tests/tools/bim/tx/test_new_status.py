"""Tests for ``CommandTxNew``, ``CommandTxStatus``, ``staleness``, ``staleness_line`` and ``_corroboration``."""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from bim.commands.tx.new import CommandTxNew
from bim.commands.tx.shared.format import NoteKind, as_datetime, body_lines, h1_titles, parse_note, read_note
from bim.commands.tx.shared.paths import TiromexPaths, iter_note_files, resolve_tiromex
from bim.commands.tx.status import CommandTxStatus, _corroboration, staleness, staleness_line
from bim.dependencies import get_repo
from buvis.pybase.zettel.application.use_cases import create_zettel_use_case

if TYPE_CHECKING:
    from pathlib import Path

    from bim.commands.tx.shared.format import TxNote

    from tests.tools.bim.tx.conftest import TxNoteBuilder, TxVault

TIMESTAMP = "%Y%m%d%H%M%S"
NO_FRONT_MATTER = "no front matter here\n"
NOW = datetime(2027, 6, 1, 12, 0, tzinfo=UTC)
CONCEPT_KEYS = ("concept-type", "assent", "lifecycle", "claims")
STATUS_KEYS = {
    "zettels",
    "notes",
    "lifecycle",
    "assent",
    "mean_links",
    "aporia",
    "open_disagreements",
    "prune_candidates",
    "pruning_enabled",
}
INDEX_ID = "20260411140000"
RUN_ID = "20260411150000"
PLAIN_ID = "20260411160000"
A_ID = "20260411145300"
B_ID = "20260412090000"
C_ID = "20260413100000"
D_ID = "20260414110000"
E_ID = "20260415120000"
F_ID = "20260416130000"
G_ID = "20260417140000"
SRC_OWN = "https://a.example/own"
SRC_OTHER = "https://b.example/other"
SRC_MIRROR = "mirror:https://c.example/copy"


def _tree(base: Path) -> list[str]:
    return sorted(path.relative_to(base).as_posix() for path in base.rglob("*"))


def _link(relation: str, note_id: str) -> str:
    return f"- {relation}:: [[notes/tiromex/{note_id}|Note {note_id}]]"


def _concept(
    tx_notes: TxNoteBuilder,
    note_id: str,
    *,
    concept_type: str = "thesis",
    assent: str | None = "tentative",
    lifecycle: str | None = "fleeting",
    extra: str = "",
    backmatter: list[str] | None = None,
    folder: Path | None = None,
) -> Path:
    """Write a concept note with the given assent, lifecycle, extra front matter and backmatter."""
    text = tx_notes.concept(note_id, f"Note {note_id}", concept_type=concept_type, claims=[], backmatter=backmatter)
    meta = (f"assent: {assent}\n" if assent else "") + (f"lifecycle: {lifecycle}\n" if lifecycle else "") + extra
    text = text.replace("assent: tentative\nlifecycle: fleeting\n", meta, 1)
    return tx_notes.write(text, note_id, folder)


def _write_state(vault: TxVault, payload: object) -> None:
    state_dir = vault.state_home / "bim" / "tx"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")


def _pairs(line: str, prefix: str) -> dict[str, int]:
    assert line.startswith(prefix)
    rest = line[len(prefix) :]
    return {key: int(value) for key, value in (item.split("=") for item in rest.split(", "))}


def _created(vault: TxVault, rel: str) -> tuple[str, TxNote]:
    text = (vault.root / rel).read_text(encoding="utf-8")
    return text, parse_note(text, rel)


@pytest.fixture
def paths(tx_vault: TxVault) -> TiromexPaths:
    return resolve_tiromex(tx_vault.zettelkasten, "tiromex")


class FakeGit:
    """Stand-in for ``subprocess.run`` that answers the work-tree probe."""

    def __init__(self) -> None:
        self.outcome: int | BaseException = 0
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        self.calls.append((list(argv), kwargs))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        code = self.outcome
        out, err = ("true\n", "") if code == 0 else ("", "fatal: not a git repository\n")
        if kwargs.get("check") and code != 0:
            raise subprocess.CalledProcessError(code, argv, out, err)
        if not (kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding")):
            return subprocess.CompletedProcess(argv, code, out.encode(), err.encode())
        return subprocess.CompletedProcess(argv, code, out, err)


@pytest.fixture
def git(monkeypatch: pytest.MonkeyPatch) -> FakeGit:
    fake = FakeGit()
    monkeypatch.setattr("bim.commands.tx.status.subprocess.run", fake)
    return fake


class TestNewDefaults:
    @pytest.mark.parametrize("title", ["Knowledge needs reasons", "Belief is not enough"])
    def test_default_note_is_a_plain_note_with_bim_fields(
        self, paths: TiromexPaths, tx_vault: TxVault, title: str
    ) -> None:
        before = datetime.now().astimezone().strftime(TIMESTAMP)
        result = CommandTxNew(paths, get_repo(), title=title).execute()
        after = datetime.now().astimezone().strftime(TIMESTAMP)

        assert result.success is True
        assert set(result.metadata) == {"id", "path"}
        note_id, rel = result.metadata["id"], result.metadata["path"]
        assert re.fullmatch(r"[0-9]{14}", note_id)
        assert before <= note_id <= after
        assert rel.startswith("notes/tiromex/")
        assert rel.endswith(".md")
        assert result.output == str(tx_vault.root / rel)
        _, note = _created(tx_vault, rel)
        meta = note.data.metadata
        assert str(meta["id"]) == note_id
        assert as_datetime(meta["date"]).astimezone().strftime(TIMESTAMP) == note_id
        assert meta["title"] == title
        assert meta["type"] == "note"
        assert meta["tags"] == []
        assert meta["publish"] is False
        assert meta["processed"] is False
        assert [key for key in CONCEPT_KEYS if key in meta] == []
        assert note.kind == NoteKind.PLAIN
        assert [file.name for file in iter_note_files(paths)] == [rel.rsplit("/", 1)[1]]

    @pytest.mark.parametrize("zettel_type", ["definition", "procedure"])
    def test_zettel_type_reaches_the_note(self, paths: TiromexPaths, tx_vault: TxVault, zettel_type: str) -> None:
        result = CommandTxNew(paths, get_repo(), title="Typed note", zettel_type=zettel_type).execute()

        assert result.success is True
        _, note = _created(tx_vault, result.metadata["path"])
        assert note.data.metadata["type"] == zettel_type

    @pytest.mark.parametrize("folder_name", ["tiromex", "atlas"])
    def test_note_lands_in_the_resolved_folder(self, tx_vault: TxVault, folder_name: str) -> None:
        paths = resolve_tiromex(tx_vault.zettelkasten, folder_name)
        paths.folder.mkdir(exist_ok=True)

        result = CommandTxNew(paths, get_repo(), title="Placed note").execute()

        assert result.success is True
        assert result.metadata["path"].startswith(f"notes/{folder_name}/")
        assert (paths.folder / result.metadata["path"].rsplit("/", 1)[1]).is_file()

    @pytest.mark.parametrize(
        ("concept_type", "title"),
        [("question", "Is knowledge possible"), ("thesis", "Knowledge needs reasons")],
    )
    def test_created_file_has_exactly_one_h1_and_no_other_body(
        self, paths: TiromexPaths, tx_vault: TxVault, concept_type: str, title: str
    ) -> None:
        result = CommandTxNew(paths, get_repo(), title=title, concept_type=concept_type).execute()

        text, note = _created(tx_vault, result.metadata["path"])
        assert h1_titles(note.body) == [title]
        assert body_lines(note.body) == [f"# {title}"]
        assert [line for line in text.splitlines() if line.startswith("# ")] == [f"# {title}"]


class TestNewConcept:
    @pytest.mark.parametrize(
        ("concept_type", "claim_bearing"),
        [
            ("thesis", True),
            ("argument", True),
            ("observation", True),
            ("aporia", False),
            ("question", False),
            ("example", False),
        ],
    )
    def test_concept_fields_and_starter_claim(
        self, paths: TiromexPaths, tx_vault: TxVault, concept_type: str, claim_bearing: bool
    ) -> None:
        title = f"A {concept_type} about grounds"

        result = CommandTxNew(paths, get_repo(), title=title, concept_type=concept_type).execute()

        assert result.success is True
        _, note = _created(tx_vault, result.metadata["path"])
        meta = note.data.metadata
        assert note.kind == NoteKind.CONCEPT
        assert meta["concept-type"] == concept_type
        assert meta["assent"] == "tentative"
        assert meta["lifecycle"] == "fleeting"
        assert meta["type"] == "note"
        if claim_bearing:
            assert meta["claims"] == [{"id": "c1", "statement": title}]
        else:
            assert "claims" not in meta

    def test_concept_type_combines_with_zettel_type(self, paths: TiromexPaths, tx_vault: TxVault) -> None:
        result = CommandTxNew(
            paths, get_repo(), title="Knowledge defined", zettel_type="definition", concept_type="argument"
        ).execute()

        _, note = _created(tx_vault, result.metadata["path"])
        assert note.data.metadata["type"] == "definition"
        assert note.data.metadata["concept-type"] == "argument"
        assert note.data.metadata["claims"] == [{"id": "c1", "statement": "Knowledge defined"}]


class TestNewRefusals:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"zettel_type": "wiki-article"},
            {"zettel_type": "notes"},
            {"zettel_type": "index"},
            {"zettel_type": "tx-run"},
            {"zettel_type": ""},
            {"concept_type": "Thesis"},
            {"concept_type": "theses"},
            {"concept_type": "doubt"},
            {"zettel_type": "wiki-article", "concept_type": "thesis"},
        ],
    )
    def test_invalid_type_writes_nothing(self, paths: TiromexPaths, tx_vault: TxVault, kwargs: dict[str, str]) -> None:
        before = _tree(tx_vault.root)

        result = CommandTxNew(paths, get_repo(), title="Never written", **kwargs).execute()

        assert result.success is False
        assert result.error
        assert result.output is None
        assert _tree(tx_vault.root) == before

    def test_unwritable_folder_gives_a_failed_result(self, tx_vault: TxVault) -> None:
        tx_vault.folder.rmdir()
        tx_vault.folder.write_text("not a directory\n", encoding="utf-8")
        paths = resolve_tiromex(tx_vault.zettelkasten, "tiromex")

        result = CommandTxNew(paths, get_repo(), title="Blocked note").execute()

        assert result.success is False
        assert result.error
        assert tx_vault.folder.read_text(encoding="utf-8") == "not a directory\n"


class TestNewCollision:
    def test_two_notes_in_one_second_get_different_ids(
        self, paths: TiromexPaths, tx_vault: TxVault, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_sleep = time.sleep
        waits: list[float] = []

        def wait_for_next_second(seconds: float) -> None:
            waits.append(seconds)
            start = datetime.now().replace(microsecond=0)
            while datetime.now().replace(microsecond=0) == start:
                real_sleep(0.005)

        while datetime.now().microsecond > 600_000:
            real_sleep(0.005)
        monkeypatch.setattr(create_zettel_use_case.time, "sleep", wait_for_next_second)

        first = CommandTxNew(paths, get_repo(), title="First in the second").execute()
        second = CommandTxNew(paths, get_repo(), title="Second in the second").execute()

        assert first.success is True
        assert second.success is True
        assert first.metadata["id"] < second.metadata["id"]
        assert first.metadata["path"] != second.metadata["path"]
        assert waits
        assert all(seconds == 1 for seconds in waits)
        assert _created(tx_vault, first.metadata["path"])[1].data.metadata["title"] == "First in the second"
        assert _created(tx_vault, second.metadata["path"])[1].data.metadata["title"] == "Second in the second"
        assert len(iter_note_files(paths)) == 2


class TestStaleness:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            (None, ("never", None)),
            ({"last_maintain": ""}, ("never", None)),
            ({"last_maintain": "not a date"}, ("unparseable", None)),
            ({"last_maintain": "2027-13-01T10:00:00+00:00"}, ("unparseable", None)),
        ],
        ids=["missing", "empty", "junk", "bad-month"],
    )
    def test_unusable_last_maintain(self, tx_vault: TxVault, payload: object, expected: tuple[str, int | None]) -> None:
        if payload is not None:
            _write_state(tx_vault, payload)

        assert staleness(NOW, 7) == expected

    @pytest.mark.parametrize(
        ("days", "window", "expected"),
        [
            (10, 7, ("stale", 10)),
            (8, 7, ("stale", 8)),
            (7, 7, ("fresh", 7)),
            (3, 7, ("fresh", 3)),
            (10, 14, ("fresh", 10)),
            (30, 14, ("stale", 30)),
        ],
    )
    def test_days_against_the_window(
        self, tx_vault: TxVault, days: int, window: int, expected: tuple[str, int | None]
    ) -> None:
        _write_state(tx_vault, {"last_maintain": (NOW - timedelta(days=days)).isoformat()})

        assert staleness(NOW, window) == expected

    def test_now_reaches_the_day_count(self, tx_vault: TxVault) -> None:
        _write_state(tx_vault, {"last_maintain": NOW.isoformat()})

        assert staleness(NOW + timedelta(days=2), 7) == ("fresh", 2)
        assert staleness(NOW + timedelta(days=9), 7) == ("stale", 9)

    @pytest.mark.parametrize(
        ("payload", "window", "expected"),
        [
            (None, 7, (True, "maintenance: never run (stale)")),
            ({"last_maintain": ""}, 7, (True, "maintenance: never run (stale)")),
            ({"last_maintain": "not a date"}, 7, (True, "maintenance: last_maintain unparseable (stale)")),
            ({"days": 10}, 7, (True, "maintenance: last run 10d ago (stale, window 7d)")),
            ({"days": 30}, 14, (True, "maintenance: last run 30d ago (stale, window 14d)")),
            ({"days": 3}, 7, (False, "maintenance: last run 3d ago (fresh)")),
            ({"days": 10}, 14, (False, "maintenance: last run 10d ago (fresh)")),
        ],
    )
    def test_staleness_line_texts(
        self, tx_vault: TxVault, payload: dict[str, Any] | None, window: int, expected: tuple[bool, str]
    ) -> None:
        if payload is not None and "days" in payload:
            payload = {"last_maintain": (NOW - timedelta(days=payload["days"])).isoformat()}
        if payload is not None:
            _write_state(tx_vault, payload)

        assert staleness_line(NOW, window) == expected


class TestCorroboration:
    def _notes(self, paths: TiromexPaths, tx_notes: TxNoteBuilder, supporter_sources: str) -> list[TxNote]:
        _concept(tx_notes, A_ID, backmatter=[f"- source:: {SRC_OWN}"])
        _concept(tx_notes, B_ID, backmatter=[_link("supports", A_ID), f"- source:: {supporter_sources}"])
        _concept(tx_notes, C_ID, backmatter=[_link("contradicts", A_ID), "- source:: https://z.example/contra"])
        _concept(tx_notes, D_ID, backmatter=[_link("supports", A_ID[:-1]), "- source:: https://w.example/prefix"])
        return [read_note(paths, file) for file in iter_note_files(paths)]

    @pytest.mark.parametrize(
        ("supporter_sources", "expected"),
        [
            (SRC_OWN, set()),
            (SRC_OTHER, {SRC_OTHER}),
            (f"{SRC_OTHER}, {SRC_MIRROR}", {SRC_OTHER, SRC_MIRROR}),
            (f"{SRC_OWN}, {SRC_MIRROR}", {SRC_MIRROR}),
        ],
        ids=["own-source", "other-source", "two-sources", "own-plus-mirror"],
    )
    def test_supporter_sources_minus_own_sources(
        self, paths: TiromexPaths, tx_notes: TxNoteBuilder, supporter_sources: str, expected: set[str]
    ) -> None:
        notes = self._notes(paths, tx_notes, supporter_sources)
        [target] = [note for note in notes if note.path == f"notes/tiromex/{A_ID}.md"]

        assert _corroboration(target, notes) == expected

    def test_no_supporters_gives_an_empty_set(self, paths: TiromexPaths, tx_notes: TxNoteBuilder) -> None:
        notes = self._notes(paths, tx_notes, SRC_OTHER)
        [target] = [note for note in notes if note.path == f"notes/tiromex/{A_ID}.md"]

        assert _corroboration(target, []) == set()
        assert _corroboration(target, [target]) == set()


@pytest.fixture
def status_vault(tx_vault: TxVault, tx_notes: TxNoteBuilder) -> TxVault:
    """Write one index, run and plain note, four concept notes, two broken files and outside notes."""
    tx_notes.write(tx_notes.index(), INDEX_ID)
    tx_notes.write(tx_notes.run(), RUN_ID)
    plain = tx_notes.plain().replace("processed: false\n", "processed: false\nlifecycle: evergreen\nassent: accepted\n")
    tx_notes.write(plain, PLAIN_ID)
    _concept(tx_notes, A_ID, backmatter=[_link("supports", B_ID)])
    _concept(
        tx_notes,
        B_ID,
        concept_type="aporia",
        assent="accepted",
        lifecycle="literature",
        extra="doubts:\n  - mode: regress\n    claim: c1\n    rationale: grounds need grounds\n",
    )
    _concept(
        tx_notes,
        C_ID,
        concept_type="question",
        assent="rejected",
        lifecycle=None,
        backmatter=[_link("contradicts", A_ID), _link("causes", B_ID)],
    )
    _concept(tx_notes, D_ID)
    tx_notes.write(NO_FRONT_MATTER, "broken")
    tx_notes.write(NO_FRONT_MATTER, "zz-broken")
    _concept(tx_notes, E_ID, concept_type="aporia", folder=tx_vault.zettelkasten / "other")
    _concept(tx_notes, F_ID, concept_type="aporia", folder=tx_vault.zettelkasten / "tiromex-old")
    _write_state(tx_vault, {"last_maintain": (NOW - timedelta(days=10)).isoformat()})
    return tx_vault


class TestStatusOutput:
    def test_lines_in_order_for_a_populated_folder(
        self, paths: TiromexPaths, status_vault: TxVault, git: FakeGit
    ) -> None:
        result = CommandTxStatus(paths, maintenance_window_days=14, pruning_enabled=True, now=NOW).execute()

        assert result.success is True
        lines = result.output.splitlines()
        assert len(lines) == 9
        assert lines[0] == f"tiromex: {paths.folder}"
        assert lines[1] == "notes: 7 (concept: 4, index: 1, runs: 1, plain: 1)"
        assert _pairs(lines[2], "lifecycle: ") == {"fleeting": 2, "literature": 1}
        assert _pairs(lines[3], "assent: ") == {"tentative": 2, "accepted": 1, "rejected": 1}
        assert lines[4] == "mean links/note: 0.75"
        assert lines[5] == "aporia notes: 1  open disagreement doubts: 0"
        assert lines[6] == "prune candidates: 1 (deletion enabled)"
        assert lines[7] == "git: tracked"
        assert lines[8] == "maintenance: last run 10d ago (fresh)"
        assert lines[8] == staleness_line(NOW, 14)[1]

    def test_metadata_keys_and_values(self, paths: TiromexPaths, status_vault: TxVault, git: FakeGit) -> None:
        result = CommandTxStatus(paths, now=NOW).execute()

        meta = result.metadata
        assert set(meta) == STATUS_KEYS
        assert meta["zettels"] == 4
        assert meta["notes"] == 7
        assert dict(meta["lifecycle"]) == {"fleeting": 2, "literature": 1}
        assert dict(meta["assent"]) == {"tentative": 2, "accepted": 1, "rejected": 1}
        assert meta["mean_links"] == 0.75
        assert meta["aporia"] == 1
        assert meta["open_disagreements"] == 0
        assert meta["prune_candidates"] == 1
        assert meta["pruning_enabled"] is False
        assert result.output.splitlines()[6] == "prune candidates: 1 (deletion report-only)"
        assert result.output.splitlines()[8] == "maintenance: last run 10d ago (stale, window 7d)"

    def test_each_unparseable_file_becomes_one_warning(
        self, paths: TiromexPaths, status_vault: TxVault, git: FakeGit
    ) -> None:
        result = CommandTxStatus(paths, now=NOW).execute()

        assert result.success is True
        assert len(result.warnings) == 2
        for stem in ("broken", "zz-broken"):
            assert len([warning for warning in result.warnings if f"notes/tiromex/{stem}.md" in warning]) == 1
        assert "broken" not in result.output

    @pytest.mark.parametrize("folder_name", ["tiromex", "atlas"])
    def test_empty_folder(self, tx_vault: TxVault, git: FakeGit, folder_name: str) -> None:
        paths = resolve_tiromex(tx_vault.zettelkasten, folder_name)
        paths.folder.mkdir(exist_ok=True)
        git.outcome = 128

        result = CommandTxStatus(paths, now=NOW).execute()

        assert result.output.splitlines() == [
            f"tiromex: {paths.folder}",
            "notes: 0 (concept: 0, index: 0, runs: 0, plain: 0)",
            "lifecycle: (none)",
            "assent: (none)",
            "mean links/note: 0.0",
            "aporia notes: 0  open disagreement doubts: 0",
            "prune candidates: 0 (deletion report-only)",
            "git: NOT a git work tree",
            "maintenance: never run (stale)",
        ]
        assert result.metadata["zettels"] == 0
        assert result.metadata["mean_links"] == 0.0
        assert result.warnings == []


class TestStatusGit:
    @pytest.mark.parametrize(
        ("outcome", "line"),
        [
            (0, "git: tracked"),
            (128, "git: NOT a git work tree"),
            (FileNotFoundError("git"), "git: NOT a git work tree"),
            (subprocess.TimeoutExpired(["git"], 10), "git: NOT a git work tree"),
        ],
        ids=["work-tree", "not-a-repo", "no-git", "timeout"],
    )
    def test_git_line_follows_the_probe(
        self, paths: TiromexPaths, git: FakeGit, outcome: int | BaseException, line: str
    ) -> None:
        git.outcome = outcome

        result = CommandTxStatus(paths, now=NOW).execute()

        assert result.success is True
        assert result.output.splitlines()[7] == line
        [(argv, kwargs)] = git.calls
        assert argv[0].rsplit("/", 1)[-1] == "git"
        assert argv[1:] == ["-C", str(paths.vault_root), "rev-parse", "--is-inside-work-tree"]
        assert kwargs.get("timeout") == 10
        assert kwargs.get("capture_output") is True or kwargs.get("stdout") == subprocess.PIPE


@pytest.fixture
def prune_vault(tx_vault: TxVault, tx_notes: TxNoteBuilder) -> TxVault:
    """Write seven concept notes; only A (by date) and G (by updated) can age into candidates."""
    _concept(tx_notes, A_ID)
    _concept(tx_notes, B_ID, concept_type="aporia", assent="rejected")
    _concept(tx_notes, C_ID, concept_type="aporia", lifecycle="evergreen")
    _concept(tx_notes, D_ID, backmatter=[_link("contradicts", E_ID)])
    _concept(tx_notes, E_ID)
    _concept(tx_notes, F_ID, extra="delivered-as: essay-2026\n")
    _concept(tx_notes, G_ID, extra="updated: 2027-05-01T10:00:00+02:00\n")
    return tx_vault


class TestStatusPrune:
    @pytest.mark.parametrize(("window", "expected"), [(365, 1), (500, 0), (20, 2)])
    def test_prune_candidates_follow_the_window_and_anchor(
        self, paths: TiromexPaths, prune_vault: TxVault, git: FakeGit, window: int, expected: int
    ) -> None:
        result = CommandTxStatus(paths, prune_window_days=window, now=NOW).execute()

        assert result.metadata["prune_candidates"] == expected
        assert result.output.splitlines()[6] == f"prune candidates: {expected} (deletion report-only)"
        assert result.metadata["zettels"] == 7
        assert result.metadata["mean_links"] == 0.14
        assert result.metadata["aporia"] == 2
        assert result.output.splitlines()[4] == "mean links/note: 0.14"

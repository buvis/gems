from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from bim.commands.doc.shared.state_db import (
    DedupResult,
    OriginalRow,
    ProcessedRow,
    open_state_db,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "subdir" / "state.db"


def _sample_processed(sha: str = "deadbeef" * 8, ts: datetime | None = None) -> ProcessedRow:
    return ProcessedRow(
        sha256=sha,
        canonical_filename="20210311083422-cez-as-7102105594.invoice.pdf",
        issuer_slug="cez-as",
        doc_type="invoice",
        processed_at=ts or datetime.now(timezone.utc),
        extraction_method="rule:cez-invoice-2024:v1",
    )


def _sample_original(sha: str = "deadbeef" * 8, ts: datetime | None = None) -> OriginalRow:
    return OriginalRow(
        original_sha256=sha,
        path=Path("/tmp/originals/20260504-deadbeef.pdf"),
        operation="reocr",
        created_at=ts or datetime.now(timezone.utc),
    )


class TestSchemaCreation:
    def test_creates_parent_dirs(self, db_path: Path) -> None:
        with open_state_db(db_path):
            assert db_path.parent.exists()

    def test_schema_version_present(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            assert row[0] is not None and row[0] >= 1

    def test_processed_table_exists(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed'")
            assert cursor.fetchone() is not None

    def test_originals_table_exists(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='originals'")
            assert cursor.fetchone() is not None

    def test_wal_mode_enabled(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("PRAGMA journal_mode")
            assert cursor.fetchone()[0].lower() == "wal"


class TestDedup:
    def test_miss_returns_no_duplicate(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            result = db.dedup("nonexistent" * 8)
            assert isinstance(result, DedupResult)
            assert result.is_duplicate is False
            assert result.existing_row is None

    def test_hit_after_record(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            row = _sample_processed()
            db.record_processed(row)
            result = db.dedup(row.sha256)
            assert result.is_duplicate is True
            assert result.existing_row is not None
            assert result.existing_row.canonical_filename == row.canonical_filename


class TestRecordProcessedIdempotency:
    def test_insert_twice_same_sha_keeps_one_row(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            row = _sample_processed()
            db.record_processed(row)
            updated = ProcessedRow(
                sha256=row.sha256,
                canonical_filename="other-name.invoice.pdf",
                issuer_slug=row.issuer_slug,
                doc_type=row.doc_type,
                processed_at=row.processed_at,
                extraction_method="llm:qwen2.5",
            )
            db.record_processed(updated)
            result = db.dedup(row.sha256)
            assert result.is_duplicate is True
            assert result.existing_row is not None
            assert result.existing_row.canonical_filename == "other-name.invoice.pdf"
            assert result.existing_row.extraction_method == "llm:qwen2.5"

            cursor = db.connection.execute("SELECT COUNT(*) FROM processed WHERE sha256 = ?", (row.sha256,))
            assert cursor.fetchone()[0] == 1


class TestRecordOriginal:
    def test_append_two_rows(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            db.record_original(_sample_original(sha="a" * 64))
            db.record_original(_sample_original(sha="b" * 64))
            cursor = db.connection.execute("SELECT COUNT(*) FROM originals")
            assert cursor.fetchone()[0] == 2


class TestPersistence:
    def test_reopen_preserves_data(self, db_path: Path) -> None:
        row = _sample_processed()
        with open_state_db(db_path) as db:
            db.record_processed(row)

        with open_state_db(db_path) as db:
            result = db.dedup(row.sha256)
            assert result.is_duplicate is True


class TestClaim:
    def test_claims_table_exists(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='claims'")
            assert cursor.fetchone() is not None

    def test_first_claim_succeeds(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            assert db.claim("a" * 64) is True

    def test_second_claim_on_same_sha_fails(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            assert db.claim("a" * 64) is True
            assert db.claim("a" * 64) is False

    def test_claim_after_record_processed_fails(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            row = _sample_processed(sha="b" * 64)
            db.record_processed(row)
            assert db.claim(row.sha256) is False

    def test_independent_shas_can_both_claim(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            assert db.claim("c" * 64) is True
            assert db.claim("d" * 64) is True

    def test_claim_persists_across_reopen(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            assert db.claim("e" * 64) is True
        with open_state_db(db_path) as db:
            assert db.claim("e" * 64) is False


class TestReleaseClaim:
    def test_release_then_reclaim(self, db_path: Path) -> None:
        sha = "f" * 64
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            assert db.release_claim(sha) is True
            assert db.claim(sha) is True

    def test_release_nonexistent_returns_false(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            assert db.release_claim("g" * 64) is False

    def test_release_after_record_processed_returns_false(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            row = _sample_processed(sha="aa" * 32)
            db.record_processed(row)
            # No claim was ever inserted, so release_claim has nothing to remove
            assert db.release_claim(row.sha256) is False

    def test_release_persists(self, db_path: Path) -> None:
        sha = "i" * 64
        with open_state_db(db_path) as db:
            db.claim(sha)
            db.release_claim(sha)
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True


class TestClaimStaleness:
    """``is_claim_stale`` answers whether a claim row is older than max_age.

    ``now`` is injected so the boundary is deterministic (no sleeping).
    """

    def test_missing_claim_row_is_not_stale(self, db_path: Path) -> None:
        # Nothing to reclaim when no worker ever claimed the sha.
        with open_state_db(db_path) as db:
            assert db.is_claim_stale("a" * 64, timedelta(minutes=60)) is False

    @pytest.mark.parametrize("max_age", [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=60)])
    def test_claim_exactly_max_age_old_is_not_stale(self, db_path: Path, max_age: timedelta) -> None:
        sha = "b" * 64
        claimed_at = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                (claimed_at.isoformat(), sha),
            )
            # Strict greater-than: an age of exactly max_age is still active.
            assert db.is_claim_stale(sha, max_age, now=claimed_at + max_age) is False

    @pytest.mark.parametrize("max_age", [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=60)])
    def test_claim_one_second_past_max_age_is_stale(self, db_path: Path, max_age: timedelta) -> None:
        """The boundary tracks the caller's max_age, not a fixed threshold.

        A one-minute max_age must call a five-minute-old claim stale; a
        hardcoded internal cutoff would only satisfy one of these cases.
        """
        sha = "c" * 64
        claimed_at = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                (claimed_at.isoformat(), sha),
            )
            assert db.is_claim_stale(sha, max_age, now=claimed_at + max_age + timedelta(seconds=1)) is True

    def test_short_max_age_makes_a_five_minute_old_claim_stale(self, db_path: Path) -> None:
        """A claim well younger than an hour is stale under a one-minute max_age."""
        sha = "ba" * 32
        claimed_at = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                (claimed_at.isoformat(), sha),
            )
            now = claimed_at + timedelta(minutes=5)
            assert db.is_claim_stale(sha, timedelta(minutes=1), now=now) is True
            # Same claim, same instant, a max_age it has not outlived yet.
            assert db.is_claim_stale(sha, timedelta(minutes=10), now=now) is False

    def test_naive_now_is_treated_as_utc(self, db_path: Path) -> None:
        """A tzinfo-less ``now`` must not raise and must mean UTC.

        ``claimed_at`` is stored tz-aware, so subtracting a naive ``now``
        without coercion raises TypeError. Reading it as local time instead
        of UTC shifts the age by the host's offset, which flips these
        one-second-boundary asserts on any non-UTC machine.
        """
        sha = "d" * 64
        max_age = timedelta(minutes=60)
        claimed_at = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
        aware_now = claimed_at + max_age + timedelta(seconds=1)
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                (claimed_at.isoformat(), sha),
            )
            assert db.is_claim_stale(sha, max_age, now=aware_now.replace(tzinfo=None)) is True
            assert db.is_claim_stale(sha, max_age, now=aware_now) is True
            # Same naive path, other side of the boundary.
            assert db.is_claim_stale(sha, max_age, now=(claimed_at + max_age).replace(tzinfo=None)) is False

    def test_verdict_follows_the_asked_sha_when_several_claims_coexist(self, db_path: Path) -> None:
        """Each sha is judged by its own row, not by whatever row exists.

        Two workers hold claims at once: one stale, one fresh. Answering from
        "the claims row" instead of "this sha's claims row" would give both the
        same verdict, and would call a sha nobody ever claimed stale just
        because the table is not empty.
        """
        stale_sha = "1a" * 32
        fresh_sha = "2b" * 32
        never_claimed_sha = "3c" * 32
        max_age = timedelta(minutes=60)
        now = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
        with open_state_db(db_path) as db:
            assert db.claim(stale_sha) is True
            assert db.claim(fresh_sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                ((now - max_age - timedelta(minutes=1)).isoformat(), stale_sha),
            )
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                ((now - timedelta(minutes=1)).isoformat(), fresh_sha),
            )

            assert db.is_claim_stale(stale_sha, max_age, now=now) is True
            assert db.is_claim_stale(fresh_sha, max_age, now=now) is False
            assert db.is_claim_stale(never_claimed_sha, max_age, now=now) is False

    def test_aware_now_in_non_utc_offset_is_converted_not_reinterpreted(self, db_path: Path) -> None:
        """An aware ``now`` at +05:00 names the same instant as its UTC form.

        Swapping the tzinfo instead of converting keeps the wall-clock digits
        and shifts the computed age by the offset, so a claim exactly at the
        boundary would wrongly read as five hours over it.
        """
        sha = "da" * 32
        max_age = timedelta(minutes=60)
        claimed_at = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
        boundary = (claimed_at + max_age).astimezone(timezone(timedelta(hours=5)))
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                (claimed_at.isoformat(), sha),
            )
            assert db.is_claim_stale(sha, max_age, now=boundary) is False
            assert db.is_claim_stale(sha, max_age, now=boundary + timedelta(seconds=1)) is True


class TestClaimReclaim:
    """``claim(max_age=...)`` steals a claim only once it has gone stale."""

    def test_stale_claim_is_reclaimed_with_refreshed_timestamp(self, db_path: Path) -> None:
        sha = "e" * 64
        # A five-minute-old claim is stale under a one-minute max_age: the
        # caller's value decides, not some threshold baked into claim().
        max_age = timedelta(minutes=1)
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                ((datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), sha),
            )
            before = datetime.now(timezone.utc)
            assert db.claim(sha, max_age=max_age) is True

            rows = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchall()
            assert len(rows) == 1
            # A no-op that merely returned True would leave the stale timestamp.
            assert datetime.fromisoformat(rows[0][0]) >= before

    def test_reclaim_leaves_another_shas_live_claim_untouched(self, db_path: Path) -> None:
        """Only the stale sha's own row is dropped.

        Another worker holds a fresh claim on an unrelated sha at the same
        time. Clearing the claims table wholesale would look identical from the
        reclaimer's side while silently handing that worker's document away.
        """
        stale_sha = "4d" * 32
        bystander_sha = "5e" * 32
        with open_state_db(db_path) as db:
            assert db.claim(stale_sha) is True
            assert db.claim(bystander_sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                ((datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), stale_sha),
            )
            before = db.connection.execute(
                "SELECT claimed_at FROM claims WHERE sha256 = ?", (bystander_sha,)
            ).fetchone()[0]

            assert db.claim(stale_sha, max_age=timedelta(minutes=1)) is True

            after = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (bystander_sha,)).fetchone()
            assert after is not None, "the bystander's claim row was deleted by an unrelated reclaim"
            assert after[0] == before
            # Its row survived intact, so the bystander is still claimed.
            assert db.claim(bystander_sha) is False

    def test_stale_claim_on_processed_sha_is_not_reclaimed(self, db_path: Path) -> None:
        """An already-processed sha is never reclaimable, however stale its claim.

        ``record_processed`` leaves the claims row in place, so an old claim
        plus a processed row is a reachable state. Reclaiming it would hand a
        second worker a document that is already done.
        """
        sha = "cc" * 32
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.record_processed(_sample_processed(sha=sha))
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                ((datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(), sha),
            )

            assert db.claim(sha, max_age=timedelta(minutes=60)) is False
            # Same verdict the no-max_age path already gives for a processed sha.
            assert db.claim(sha) is False

    def test_fresh_claim_is_not_reclaimed(self, db_path: Path) -> None:
        sha = "aa" * 32
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            original = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchone()[0]

            assert db.claim(sha, max_age=timedelta(minutes=60)) is False

            after = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchone()[0]
            assert after == original

    def test_ancient_claim_without_max_age_still_blocks(self, db_path: Path) -> None:
        """``max_age=None`` (the default) means no staleness check at all."""
        sha = "bb" * 32
        ancient = (datetime.now(timezone.utc) - timedelta(days=3650)).isoformat()
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute("UPDATE claims SET claimed_at = ? WHERE sha256 = ?", (ancient, sha))

            assert db.claim(sha) is False
            assert db.claim(sha, max_age=None) is False

            after = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchone()[0]
            assert after == ancient


class TestMigrationIdempotency:
    def test_reopen_idempotent(self, db_path: Path) -> None:
        # First open creates schema_version row at the current version.
        with open_state_db(db_path):
            pass
        # Second open should NOT raise IntegrityError despite the row existing.
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT COUNT(*) FROM schema_version WHERE version = 3")
            count = cursor.fetchone()[0]
            # INSERT OR IGNORE means at most one row at the current version.
            assert count == 1


class TestProcessedRowValidation:
    """sha256 on ProcessedRow must be 64 lowercase hex chars."""

    def _kwargs(self) -> dict[str, object]:
        return {
            "canonical_filename": "20210311083422-cez-as-x.invoice.pdf",
            "issuer_slug": "cez-as",
            "doc_type": "invoice",
            "processed_at": datetime.now(timezone.utc),
            "extraction_method": "manual",
        }

    def test_valid_hex64_sha_accepted(self) -> None:
        row = ProcessedRow(sha256="abcd1234" * 8, **self._kwargs())
        assert row.sha256 == "abcd1234" * 8

    def test_uppercase_sha_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProcessedRow(sha256="A" * 64, **self._kwargs())

    def test_too_short_sha_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProcessedRow(sha256="a" * 63, **self._kwargs())

    def test_too_long_sha_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProcessedRow(sha256="a" * 65, **self._kwargs())

    def test_non_hex_chars_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProcessedRow(sha256="z" * 64, **self._kwargs())

    def test_empty_sha_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ProcessedRow(sha256="", **self._kwargs())


class TestSchemaV2:
    def test_schema_version_is_current(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT MAX(version) FROM schema_version")
            assert cursor.fetchone()[0] == 3


class TestSchemaMigrationV1ToV2:
    def _build_v1_db(self, path: Path) -> None:
        """Construct a v1-shaped database manually (no claims table, version=1)."""
        import sqlite3

        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE processed (
                sha256 TEXT PRIMARY KEY,
                canonical_filename TEXT NOT NULL,
                issuer_slug TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                extraction_method TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE originals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_sha256 TEXT NOT NULL,
                path TEXT NOT NULL,
                operation TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.execute(
            """
            INSERT INTO processed
                (sha256, canonical_filename, issuer_slug, doc_type,
                 processed_at, extraction_method)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "f" * 64,
                "20210311083422-cez-as-7102105594.invoice.pdf",
                "cez-as",
                "invoice",
                datetime.now(timezone.utc).isoformat(),
                "rule:cez-invoice-2024:v1",
            ),
        )
        conn.close()

    def test_v1_to_v2_migration_adds_claims_table(self, db_path: Path) -> None:
        import sqlite3

        self._build_v1_db(db_path)

        check = sqlite3.connect(str(db_path))
        pre = check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='claims'").fetchone()
        check.close()
        assert pre is None, "v1 fixture should not have claims table"

        with open_state_db(db_path) as db:
            assert (
                db.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='claims'").fetchone()
                is not None
            )

            assert db.connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 3

            result = db.dedup("f" * 64)
            assert result.is_duplicate is True
            assert result.existing_row is not None
            assert result.existing_row.issuer_slug == "cez-as"

            assert db.claim("e" * 64) is True
            assert db.release_claim("e" * 64) is True


class TestMigrationTransaction:
    """_migrate must wrap DDL in BEGIN/COMMIT so a mid-migration crash leaves no partial state."""

    def test_failure_during_migration_rolls_back_all_ddl(self, db_path: Path, mocker: object) -> None:
        import sqlite3

        from bim.commands.doc.shared import state_db as state_db_mod

        db_path.parent.mkdir(parents=True, exist_ok=True)
        real_connect = sqlite3.connect

        class FlakyConnection:
            """Wrap a real connection but fail on the Nth execute() call."""

            def __init__(self, real_conn: sqlite3.Connection, fail_after: int) -> None:
                self._real = real_conn
                self._call = 0
                self._fail_after = fail_after

            def execute(self, sql: str, *args: object, **kwargs: object) -> object:
                self._call += 1
                if self._call > self._fail_after:
                    raise sqlite3.OperationalError("simulated mid-migration failure")
                return self._real.execute(sql, *args, **kwargs)

            def __getattr__(self, name: str) -> object:
                return getattr(self._real, name)

        real_conn = real_connect(str(db_path), isolation_level=None)
        # Allow first 5 executes (2 PRAGMAs + BEGIN + first 2 DDLs), fail on the 3rd DDL.
        # With a transaction wrapping the DDL block, ROLLBACK must undo the partially-
        # created schema_version and processed tables.
        fake_conn = FlakyConnection(real_conn, fail_after=5)
        mocker.patch.object(  # type: ignore[attr-defined]
            sqlite3,
            "connect",
            return_value=fake_conn,
        )

        with pytest.raises(sqlite3.OperationalError, match="simulated"):
            state_db_mod.StateDB.open(db_path)

        # After rollback, none of the DDL tables should exist.
        check = real_connect(str(db_path), isolation_level=None)
        try:
            for table in ("schema_version", "processed", "originals", "claims"):
                row = check.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                assert row is None, f"{table} table should not exist after rolled-back migration"
        finally:
            check.close()


class TestClaimConcurrency:
    """Verify the SQLite ``INSERT ... WHERE NOT EXISTS`` keeps ``claim()``
    atomic when multiple workers race for the same sha256.

    Worker function lives in ``_concurrency_workers.py`` (non-test module) so
    pytest's spawn-method workers do not re-trigger collection on import and
    deadlock against the SQLite WAL we're testing.
    """

    def test_only_one_winner_when_workers_race_for_same_sha(
        self, db_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import multiprocessing as mp
        import os
        import sys

        from bim.commands.doc.shared.state_db import StateDB

        # See TestRegisterIssuerConcurrency for the PYTHONPATH rationale.
        worker_dir = str(Path(__file__).parent)
        if worker_dir not in sys.path:
            sys.path.insert(0, worker_dir)
        monkeypatch.setenv(
            "PYTHONPATH",
            worker_dir + os.pathsep + os.environ.get("PYTHONPATH", ""),
        )
        import _concurrency_workers

        # Initialize the DB schema once in the parent so workers don't race
        # the migration itself (a separate concern, covered by the migration
        # tests above). Each worker re-opens its own connection.
        StateDB.open(db_path).connection.close()

        worker_count = 5
        sha = "c0ffee" * 10 + "abcd"  # 64 hex chars
        ctx = mp.get_context("spawn")
        out_queue: mp.queues.Queue[str] = ctx.Queue()
        barrier = ctx.Barrier(worker_count)
        processes = [
            ctx.Process(
                target=_concurrency_workers.claim_worker,
                args=(str(db_path), sha, out_queue, barrier),
            )
            for _ in range(worker_count)
        ]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=20)
            assert not p.is_alive(), "worker still running after timeout — SQL deadlock"
            assert p.exitcode == 0, f"worker exited with {p.exitcode}"

        results = sorted(out_queue.get_nowait() for _ in range(worker_count))
        assert results.count("true") == 1, f"expected exactly 1 winning claim, got: {results}"
        assert results.count("false") == worker_count - 1, f"expected {worker_count - 1} losing claims, got: {results}"

        # Verify exactly one row landed in the claims table.
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT COUNT(*) FROM claims WHERE sha256 = ?", (sha,))
            assert cursor.fetchone()[0] == 1


class TestRuleMatches:
    def test_table_exists_after_open(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rule_matches'")
            assert cursor.fetchone() is not None

    def test_get_returns_empty_dict_when_no_matches(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            assert db.get_rule_last_matches() == {}

    def test_record_then_get_round_trip(self, db_path: Path) -> None:
        t1 = datetime.now(timezone.utc)
        with open_state_db(db_path) as db:
            db.record_rule_match("rule-a", t1)
            assert db.get_rule_last_matches() == {"rule-a": t1}

    def test_record_overwrites_existing(self, db_path: Path) -> None:
        t1 = datetime.now(timezone.utc)
        t2 = t1 + timedelta(hours=1)
        with open_state_db(db_path) as db:
            db.record_rule_match("rule-a", t1)
            db.record_rule_match("rule-a", t2)
            matches = db.get_rule_last_matches()
            assert matches == {"rule-a": t2}

    def test_multiple_rules_isolated(self, db_path: Path) -> None:
        t1 = datetime.now(timezone.utc)
        t2 = t1 + timedelta(minutes=5)
        with open_state_db(db_path) as db:
            db.record_rule_match("a", t1)
            db.record_rule_match("b", t2)
            matches = db.get_rule_last_matches()
            assert matches == {"a": t1, "b": t2}

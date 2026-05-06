from __future__ import annotations

from datetime import datetime, timezone
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


class TestMigrationIdempotency:
    def test_reopen_idempotent(self, db_path: Path) -> None:
        # First open creates schema_version row at v2.
        with open_state_db(db_path):
            pass
        # Second open should NOT raise IntegrityError despite the row existing.
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT COUNT(*) FROM schema_version WHERE version = 2")
            count = cursor.fetchone()[0]
            # INSERT OR IGNORE means at most one v2 row; could be 1 here.
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
    def test_schema_version_is_two(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT MAX(version) FROM schema_version")
            assert cursor.fetchone()[0] == 2


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

            assert db.connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 2

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

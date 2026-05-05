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
            row = _sample_processed(sha="h" * 64)
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


class TestSchemaV2:
    def test_schema_version_is_two(self, db_path: Path) -> None:
        with open_state_db(db_path) as db:
            cursor = db.connection.execute("SELECT MAX(version) FROM schema_version")
            assert cursor.fetchone()[0] == 2

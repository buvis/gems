from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType

from pydantic import BaseModel, ConfigDict
from typing_extensions import Self

__all__ = [
    "DedupResult",
    "OriginalRow",
    "ProcessedRow",
    "StateDB",
    "open_state_db",
]


class ProcessedRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str
    canonical_filename: str
    issuer_slug: str
    doc_type: str
    processed_at: datetime
    extraction_method: str


class OriginalRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    original_sha256: str
    path: Path
    operation: str
    created_at: datetime


class DedupResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_duplicate: bool
    existing_row: ProcessedRow | None


_SCHEMA_VERSION = 2

_SCHEMA_DDL = (
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS processed (
        sha256 TEXT PRIMARY KEY,
        canonical_filename TEXT NOT NULL,
        issuer_slug TEXT NOT NULL,
        doc_type TEXT NOT NULL,
        processed_at TEXT NOT NULL,
        extraction_method TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS originals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_sha256 TEXT NOT NULL,
        path TEXT NOT NULL,
        operation TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claims (
        sha256 TEXT PRIMARY KEY,
        claimed_at TEXT NOT NULL
    )
    """,
)


class StateDB:
    """SQLite-backed dedup, processing log, and originals tracker.

    Schema is created on first open. Connection uses WAL journaling and
    NORMAL synchronous to balance durability and write performance.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @classmethod
    def open(cls, path: Path) -> StateDB:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        cls._migrate(conn)
        return cls(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        for ddl in _SCHEMA_DDL:
            conn.execute(ddl)
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        current = cursor.fetchone()[0]
        if current is None or current < _SCHEMA_VERSION:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )

    def claim(self, sha256: str) -> bool:
        """Atomically claim ownership of processing this sha256.

        Returns True if this caller successfully claimed (no prior claim or
        completed processing existed). Returns False if another worker has
        already claimed or processed this sha256.

        The pipeline pattern is:
            1. dedup(sha) - skip if already in processed
            2. claim(sha) - skip if already claimed by another worker
            3. process the document
            4. record_processed(row) - finalize

        Spec section 6 step 1: "Record the hash now to prevent concurrent
        re-processing."
        """
        # Check processed first - already-finalized documents are not claimable.
        existing = self._conn.execute("SELECT 1 FROM processed WHERE sha256 = ? LIMIT 1", (sha256,)).fetchone()
        if existing is not None:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO claims (sha256, claimed_at) VALUES (?, ?)",
            (sha256, now_iso),
        )
        return cursor.rowcount == 1

    def dedup(self, sha256: str) -> DedupResult:
        cursor = self._conn.execute(
            """
            SELECT sha256, canonical_filename, issuer_slug, doc_type,
                   processed_at, extraction_method
            FROM processed WHERE sha256 = ? LIMIT 1
            """,
            (sha256,),
        )
        row = cursor.fetchone()
        if row is None:
            return DedupResult(is_duplicate=False, existing_row=None)
        existing = ProcessedRow(
            sha256=row[0],
            canonical_filename=row[1],
            issuer_slug=row[2],
            doc_type=row[3],
            processed_at=datetime.fromisoformat(row[4]),
            extraction_method=row[5],
        )
        return DedupResult(is_duplicate=True, existing_row=existing)

    def record_processed(self, row: ProcessedRow) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO processed
                (sha256, canonical_filename, issuer_slug, doc_type,
                 processed_at, extraction_method)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row.sha256,
                row.canonical_filename,
                row.issuer_slug,
                row.doc_type,
                row.processed_at.isoformat(),
                row.extraction_method,
            ),
        )

    def record_original(self, row: OriginalRow) -> None:
        self._conn.execute(
            """
            INSERT INTO originals (original_sha256, path, operation, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                row.original_sha256,
                str(row.path),
                row.operation,
                row.created_at.isoformat(),
            ),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def open_state_db(path: Path) -> StateDB:
    """Open or create the state DB at the given path."""
    return StateDB.open(path)

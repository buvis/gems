from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import TracebackType

from pydantic import BaseModel, ConfigDict, field_validator
from typing_extensions import Self

from bim.commands.doc.shared.validators import validate_sha256_hex64

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

    @field_validator("sha256")
    @classmethod
    def _sha256_is_hex64(cls, v: str) -> str:
        return validate_sha256_hex64("sha256", v)


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


_SCHEMA_VERSION = 3

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
    """
    CREATE TABLE IF NOT EXISTS rule_matches (
        rule_id TEXT PRIMARY KEY,
        last_matched_at TEXT NOT NULL
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
        # Wrap DDL + version-row insert in an explicit transaction so a crash
        # mid-migration leaves the file unchanged. SQLite supports CREATE TABLE
        # IF NOT EXISTS inside transactions and ROLLBACK reverts the schema
        # changes atomically. Connection runs in autocommit (isolation_level=None)
        # so BEGIN/COMMIT must be explicit.
        conn.execute("BEGIN")
        try:
            for ddl in _SCHEMA_DDL:
                conn.execute(ddl)
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            current = cursor.fetchone()[0]
            if current is None or current < _SCHEMA_VERSION:
                # OR IGNORE prevents IntegrityError if two processes race to
                # bump the schema version on a fresh DB.
                conn.execute(
                    "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                    (_SCHEMA_VERSION,),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _read_claim_staleness(
        self,
        sha256: str,
        max_age: timedelta,
        now: datetime | None = None,
    ) -> tuple[bool, str | None]:
        """Read the claim row once and judge it against ``max_age``.

        Returns:
            ``(stale, claimed_at)`` where ``claimed_at`` is the exact stored
            string the verdict was formed from, or ``None`` when no claim row
            exists. Handing that string back lets ``claim`` bind it in its
            delete, so a claim refreshed between the read and the delete is
            recognised as a different value and survives.
        """
        row = self._conn.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha256,)).fetchone()
        if row is None:
            return False, None
        moment = now if now is not None else datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        try:
            claimed_at = datetime.fromisoformat(row[0])
        except ValueError:
            # A stamp no parser accepts cannot vouch for a live worker, so the
            # row reads as abandoned instead of wedging its sha forever. Only
            # this one failure is absorbed: a database fault says nothing about
            # a claim's age, and calling it stale would license stealing a live
            # claim, so everything else propagates.
            return True, row[0]
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
        return moment - claimed_at > max_age, row[0]

    def is_claim_stale(
        self,
        sha256: str,
        max_age: timedelta,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Report whether this sha's claim is older than ``max_age``.

        Args:
            max_age: How long a claim stays live. A claim aged exactly
                ``max_age`` is still live; staleness is strictly older.
            now: The instant to measure against; defaults to the current UTC
                time. A tz-naive value is read as UTC.

        Returns:
            False when no claim row exists for ``sha256``. True when the stored
            ``claimed_at`` cannot be parsed. A tz-naive stored value is read as
            UTC, mirroring ``now``.
        """
        stale, _ = self._read_claim_staleness(sha256, max_age, now)
        return stale

    def claim(self, sha256: str, *, max_age: timedelta | None = None) -> bool:
        """Atomically claim ownership of processing this sha256.

        Returns True if this caller successfully claimed (no prior claim or
        completed processing existed). Returns False if another worker has
        already claimed or processed this sha256.

        The pipeline pattern is:
            1. claim(sha) - skip if already processed or claimed
            2. process the document
            3. record_processed(row) - finalize
            4. release_claim(sha) in a finally

        Spec section 6 step 1: "Record the hash now to prevent concurrent
        re-processing." Single-statement INSERT with WHERE NOT EXISTS keeps
        the check-and-claim atomic under SQLite WAL+autocommit.

        Args:
            max_age: When given, a claim on this sha older than ``max_age`` is
                treated as abandoned (its worker died without releasing it) and
                is taken over with a refreshed timestamp. ``None`` (the default)
                never reclaims: any existing claim blocks. An already-processed
                sha is never reclaimed, however old its claim.
        """
        if max_age is not None:
            stale, claimed_at = self._read_claim_staleness(sha256, max_age)
            if stale:
                # Compare-and-delete on the value the read observed. Binding it
                # verbatim is what closes the gap between the two statements: a
                # rival that reclaimed the sha meanwhile wrote a different
                # string, so its live claim no longer matches and survives.
                # Re-deriving staleness in SQL cannot do this - claimed_at is
                # TEXT, so a comparison against a cutoff sorts lexicographically
                # and a fresh claim stamped in a negative offset falls below a
                # UTC cutoff.
                self._conn.execute(
                    """
                    DELETE FROM claims
                    WHERE sha256 = ?
                      AND claimed_at = ?
                      AND NOT EXISTS (SELECT 1 FROM processed WHERE sha256 = ?)
                    """,
                    (sha256, claimed_at, sha256),
                )
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """
            INSERT OR IGNORE INTO claims (sha256, claimed_at)
            SELECT ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM processed WHERE sha256 = ?)
            """,
            (sha256, now_iso, sha256),
        )
        return cursor.rowcount == 1

    def release_claim(self, sha256: str) -> bool:
        """Release a prior claim so the sha can be re-attempted.

        Returns True if a claim row was actually removed; False if there was
        no claim to release (already processed, never claimed, or already
        released). Called from the ingest pipeline's finally, so no run leaves
        a sha256 permanently parked.
        """
        cursor = self._conn.execute("DELETE FROM claims WHERE sha256 = ?", (sha256,))
        return cursor.rowcount == 1

    def dedup(self, sha256: str) -> DedupResult:
        """Look up sha256 in the processed table.

        This is a read-only check intended for fast-path skip decisions
        (e.g., audit walks or read-only inspection). Pipeline workers MUST
        use ``claim()`` instead - ``dedup()`` does not prevent two concurrent
        workers from both observing a miss and both processing the same
        document. ``claim()`` atomically checks both the ``processed`` and
        ``claims`` tables and reserves the sha for the calling worker.
        """
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

    def record_rule_match(self, rule_id: str, matched_at: datetime) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO rule_matches (rule_id, last_matched_at) VALUES (?, ?)",
            (rule_id, matched_at.isoformat()),
        )

    def get_rule_last_matches(self) -> dict[str, datetime]:
        cursor = self._conn.execute("SELECT rule_id, last_matched_at FROM rule_matches")
        return {row[0]: datetime.fromisoformat(row[1]) for row in cursor.fetchall()}

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

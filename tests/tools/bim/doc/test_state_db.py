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

    def test_release_leaves_another_shas_live_claim_untouched(self, db_path: Path) -> None:
        """Releasing one sha frees that sha and nothing else.

        Another worker holds a live claim on an unrelated sha at the same
        time. Clearing the claims table wholesale looks identical to the
        releasing caller while silently handing that worker's document away.
        """
        released_sha = "6f" * 32
        bystander_sha = "7e" * 32
        with open_state_db(db_path) as db:
            assert db.claim(released_sha) is True
            assert db.claim(bystander_sha) is True
            held = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (bystander_sha,)).fetchone()[
                0
            ]

            # Two rows in the table, one of them ours: still a real release.
            assert db.release_claim(released_sha) is True

            after = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (bystander_sha,)).fetchone()
            assert after is not None, "the bystander's claim row was deleted by an unrelated release"
            assert after[0] == held
            # Its row survived intact, so the bystander is still held.
            assert db.claim(bystander_sha) is False
            # ...and the sha we did release really is free again.
            assert db.claim(released_sha) is True


class TestClaimStaleness:
    """``is_claim_stale`` answers whether a claim row is older than max_age.

    ``now`` is injected so the boundary is deterministic (no sleeping).
    """

    def test_missing_claim_row_is_not_stale(self, db_path: Path) -> None:
        # Nothing to reclaim when no worker ever claimed the sha.
        with open_state_db(db_path) as db:
            assert db.is_claim_stale("a" * 64, timedelta(minutes=60)) is False

    @pytest.mark.parametrize(
        "max_age",
        [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=60), timedelta(hours=25)],
    )
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

    @pytest.mark.parametrize(
        "max_age",
        [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=60), timedelta(hours=25)],
    )
    def test_claim_one_second_past_max_age_is_stale(self, db_path: Path, max_age: timedelta) -> None:
        """The boundary tracks the caller's max_age, not a fixed threshold.

        A one-minute max_age must call a five-minute-old claim stale; a
        hardcoded internal cutoff would only satisfy one of these cases.
        The day-long window matters as much as the short ones: an operator
        may configure one, and a cap baked into the implementation would
        quietly refuse to ever trust it.
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

    @pytest.mark.parametrize("max_age", [timedelta(minutes=1), timedelta(minutes=60), timedelta(hours=25)])
    def test_stale_claim_is_reclaimed_with_refreshed_timestamp(self, db_path: Path, max_age: timedelta) -> None:
        """The caller's window decides, not a threshold baked into claim().

        A claim five minutes past a one-minute window is abandoned, and so
        is one five minutes past a twenty-five-hour window. An
        implementation that quietly refuses to trust a window longer than
        some invented cap wedges every sha in such a deployment forever.
        """
        sha = "e" * 64
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                ((datetime.now(timezone.utc) - max_age - timedelta(minutes=5)).isoformat(), sha),
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

    @pytest.mark.parametrize("max_age", [timedelta(minutes=1), timedelta(minutes=60), timedelta(hours=25)])
    def test_fresh_claim_is_not_reclaimed(self, db_path: Path, max_age: timedelta) -> None:
        """The other side of the same window: a claim taken moments ago is
        live under every configured max_age, short or day-long."""
        sha = "aa" * 32
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            original = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchone()[0]

            assert db.claim(sha, max_age=max_age) is False

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


class TestReclaimRaceWindow:
    """Reclaiming must not destroy a claim that went live again meanwhile.

    Reading the age and dropping the row are two separate statements, so a
    rival worker can take the sha over in the gap between them and write a
    brand-new ``claimed_at``. A drop that carries no age condition removes
    that live claim, and both workers then process the same document.
    """

    @pytest.mark.parametrize(
        "rival_zone",
        [timezone.utc, timezone(timedelta(hours=-5))],
        ids=["rival-stamps-utc", "rival-stamps-utc-minus-5"],
    )
    def test_claim_refreshed_inside_the_reclaim_gap_is_not_destroyed(self, db_path: Path, rival_zone: timezone) -> None:
        """The rival's own offset must not decide whether its claim survives.

        A worker in a non-UTC zone stamps ``2026-08-15T19:50:17-05:00`` for
        the same instant a UTC worker writes as ``2026-08-16T00:50:17+00:00``.
        Sorted as text the first one falls BELOW a UTC cutoff, so a drop that
        re-derives staleness by comparing strings destroys a claim taken one
        second ago. Only matching the exact value the staleness read observed
        survives both stampings.
        """
        import sqlite3

        from bim.commands.doc.shared.state_db import StateDB

        sha = "7a" * 32
        control_sha = "7b" * 32
        # Abandoned half an hour ago, so the reclaim branch is entered.
        stale_claimed_at = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()

        class BufferedCursor:
            """Serve rows already drained from a real cursor."""

            def __init__(self, rows: list[tuple[object, ...]], rowcount: int) -> None:
                self._rows = list(rows)
                self.rowcount = rowcount

            def fetchone(self) -> tuple[object, ...] | None:
                return self._rows.pop(0) if self._rows else None

            def fetchall(self) -> list[tuple[object, ...]]:
                rows, self._rows = self._rows, []
                return rows

        class InterloperConnection:
            """Wrap a real connection and slip a rival's claim into the gap.

            The rival fires the instant a statement hands back the abandoned
            ``claimed_at``: that read is where the gap opens, and its result
            is what the caller is about to act on. Keying on the value
            observed rather than on statement text means neither a decoy read
            that returns nothing nor a ``WHERE 1 = 0`` write can spring the
            trap early and defuse it. ``total_changes`` is sampled around
            every statement, so a write that matched no row is not mistaken
            for work. Same wrapping trick as ``FlakyConnection`` below, so
            the race is deterministic: no sleeping, no second process.
            """

            def __init__(self, real_conn: sqlite3.Connection) -> None:
                self._real = real_conn
                self.rival_claimed_at: str | None = None
                self.rival_rows_changed = 0
                self.rows_changed_after_rival = 0

            def execute(self, sql: str, *args: object, **kwargs: object) -> object:
                before = self._real.total_changes
                cursor = self._real.execute(sql, *args, **kwargs)
                if self.rival_claimed_at is not None:
                    self.rows_changed_after_rival += self._real.total_changes - before
                    return cursor
                if not " ".join(sql.split()).upper().startswith("SELECT"):
                    return cursor
                rows = cursor.fetchall()
                if any(stale_claimed_at in row for row in rows):
                    # The caller is holding the stale verdict now. Take the
                    # sha over before it can act on it.
                    self.rival_claimed_at = datetime.now(rival_zone).isoformat()
                    mark = self._real.total_changes
                    self._real.execute(
                        "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                        (self.rival_claimed_at, sha),
                    )
                    self.rival_rows_changed = self._real.total_changes - mark
                return BufferedCursor(rows, cursor.rowcount)

            def __getattr__(self, name: str) -> object:
                return getattr(self._real, name)

        with open_state_db(db_path) as db:
            # Control: on the same seeded state, with nobody racing, the
            # reclaim really does rewrite the table. A "reclaim" that matches
            # no row cannot satisfy this, so a row surviving the race below
            # cannot be credited to a statement that never did anything.
            assert db.claim(control_sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                (stale_claimed_at, control_sha),
            )
            changes_before = db.connection.total_changes
            assert db.claim(control_sha, max_age=timedelta(minutes=1)) is True
            assert db.connection.total_changes - changes_before >= 1, "the reclaim changed no row at all"

            assert db.claim(sha) is True
            db.connection.execute(
                "UPDATE claims SET claimed_at = ? WHERE sha256 = ?",
                (stale_claimed_at, sha),
            )

            racing = InterloperConnection(db.connection)
            won = StateDB(racing).claim(sha, max_age=timedelta(minutes=1))

            assert racing.rival_claimed_at is not None, "nothing ever read the stale stamp; the gap never opened"
            assert racing.rival_rows_changed == 1, "the rival's takeover never landed, so no live claim was at risk"
            row = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchone()
            assert row is not None, "the rival worker's live claim row was deleted"
            # A surviving row is not enough: a reclaim that dropped the rival's
            # row and inserted its own leaves the table looking identical.
            assert row[0] == racing.rival_claimed_at, "the rival's live claim was replaced by the reclaimer's own"
            assert racing.rows_changed_after_rival == 0, "the reclaimer still wrote to a sha it no longer owned"
            assert won is False, "the sha was claimed again before the drop, so this caller must lose"


_UNPARSEABLE_CLAIMED_AT = ("", "not-a-timestamp", "2026-02-30T12:00:00+00:00", "null")


class TestClaimedAtParsing:
    """Whatever the ``claims`` table happens to hold must not blow up a run.

    A hand-edited state file, a restored backup, or another writer can leave
    a ``claimed_at`` no ISO-8601 parser accepts, or one with no timezone at
    all. The ingest pipeline calls ``claim()`` before its own try block, so
    an escaping ValueError or TypeError reaches the user as a stack trace.
    """

    @pytest.mark.parametrize("claimed_at", _UNPARSEABLE_CLAIMED_AT)
    def test_unparseable_claimed_at_reads_as_stale(self, db_path: Path, claimed_at: str) -> None:
        """A timestamp nobody can read cannot be trusted to mean "live", so the
        row counts as abandoned rather than wedging its sha forever."""
        sha = "8b" * 32
        with open_state_db(db_path) as db:
            db.connection.execute(
                "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
                (sha, claimed_at),
            )
            now = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
            assert db.is_claim_stale(sha, timedelta(minutes=60), now=now) is True

    def test_tz_naive_stored_claimed_at_is_read_as_utc(self, db_path: Path) -> None:
        """A stored ``claimed_at`` without an offset must mean UTC.

        Subtracting a naive stored value from an aware ``now`` raises
        TypeError; reading it as local time instead of UTC shifts the age by
        the host's offset and flips this one-second boundary pair on any
        non-UTC machine. Mirrors the coercion already applied to ``now``.
        """
        sha = "9c" * 32
        max_age = timedelta(minutes=60)
        stored_naive = datetime(2026, 5, 4, 12, 0)
        with open_state_db(db_path) as db:
            db.connection.execute(
                "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
                (sha, stored_naive.isoformat()),
            )
            boundary = datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc)
            assert db.is_claim_stale(sha, max_age, now=boundary) is False
            assert db.is_claim_stale(sha, max_age, now=boundary + timedelta(seconds=1)) is True

    @pytest.mark.parametrize("claimed_at", [*_UNPARSEABLE_CLAIMED_AT, "2026-05-04T12:00:00"])
    def test_claim_takes_over_an_untrustworthy_row_instead_of_raising(self, db_path: Path, claimed_at: str) -> None:
        """``claim()`` runs outside the pipeline's try block, so anything raised
        here surfaces as a raw stack trace. A row nobody can read counts as
        abandoned, so this caller must win it - anything else wedges the sha
        forever. The takeover has to be complete: one row left, stamped with a
        live UTC time of this caller's own, not the value it distrusted. Its
        blast radius stops at that row: a healthy claim another worker holds
        on an unrelated sha must come through untouched."""
        sha = "ad" * 32
        bystander_sha = "bd" * 32
        max_age = timedelta(minutes=60)
        with open_state_db(db_path) as db:
            db.connection.execute(
                "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
                (sha, claimed_at),
            )
            assert db.claim(bystander_sha) is True
            held = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (bystander_sha,)).fetchone()[
                0
            ]

            before = datetime.now(timezone.utc)
            assert db.claim(sha, max_age=max_age) is True
            after = datetime.now(timezone.utc)

            # The sha may not be left unclaimed either: dropping the row
            # without taking it over would hand the document to the next two
            # workers at once.
            rows = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchall()
            assert len(rows) == 1
            assert rows[0][0] != claimed_at, "the distrusted value survived, so the sha was never really taken over"

            # Must parse, or the next reader inherits the same problem.
            stamped = datetime.fromisoformat(rows[0][0])
            assert stamped.utcoffset() == timedelta(0), "a claim with no offset is the bug this row already had"
            # One second of slack absorbs a stamp truncated to whole seconds.
            assert before - timedelta(seconds=1) <= stamped <= after + timedelta(seconds=1)

            surviving = db.connection.execute(
                "SELECT claimed_at FROM claims WHERE sha256 = ?", (bystander_sha,)
            ).fetchone()
            assert surviving is not None, "a bystander's healthy claim was swept up by the takeover"
            assert surviving[0] == held
            assert db.claim(bystander_sha) is False

    @pytest.mark.parametrize("claimed_at", [*_UNPARSEABLE_CLAIMED_AT, "2026-05-04T12:00:00"])
    def test_untrustworthy_claim_on_a_processed_sha_is_not_taken_over(self, db_path: Path, claimed_at: str) -> None:
        """A finished document is never handed out again, however corrupt its
        claim row. Distrusting the timestamp says nothing about the ``processed``
        table, so the completed-work guard has to survive the takeover path -
        the twin of ``test_stale_claim_on_processed_sha_is_not_reclaimed``."""
        sha = "be" * 32
        with open_state_db(db_path) as db:
            db.record_processed(_sample_processed(sha=sha))
            db.connection.execute(
                "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
                (sha, claimed_at),
            )

            assert db.claim(sha, max_age=timedelta(minutes=60)) is False
            # Same verdict the no-max_age path already gives for a processed sha.
            assert db.claim(sha) is False
            assert db.dedup(sha).is_duplicate is True

    def test_blob_claimed_at_reads_as_stale(self, db_path: Path) -> None:
        """A ``claimed_at`` stored as a BLOB comes back as ``bytes`` - a
        different failure path than the corrupt-text cases above - but the
        same verdict applies: a stamp nobody can read cannot vouch for a live
        worker, so the row counts as abandoned rather than raising."""
        import sqlite3

        sha = "af" * 32
        with open_state_db(db_path) as db:
            db.connection.execute(
                "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
                (sha, sqlite3.Binary(b"\x00\x01")),
            )
            now = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
            assert db.is_claim_stale(sha, timedelta(minutes=60), now=now) is True

    def test_claim_takes_over_a_blob_claimed_at_row(self, db_path: Path) -> None:
        """``claim()`` must win a BLOB-valued row rather than raising:
        anything raised here surfaces as a raw stack trace, and a row nobody
        can read must not wedge its sha forever. The takeover has to be
        complete: one row left, stamped with a fresh, parseable UTC time."""
        import sqlite3

        sha = "bf" * 32
        with open_state_db(db_path) as db:
            db.connection.execute(
                "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
                (sha, sqlite3.Binary(b"\x00\x01")),
            )
            before = datetime.now(timezone.utc)
            assert db.claim(sha, max_age=timedelta(minutes=60)) is True
            after = datetime.now(timezone.utc)

            rows = db.connection.execute("SELECT claimed_at FROM claims WHERE sha256 = ?", (sha,)).fetchall()
            assert len(rows) == 1
            # Must parse, or the next reader inherits the same problem.
            stamped = datetime.fromisoformat(rows[0][0])
            assert stamped.utcoffset() == timedelta(0)
            # One second of slack absorbs a stamp truncated to whole seconds.
            assert before - timedelta(seconds=1) <= stamped <= after + timedelta(seconds=1)

    def test_blob_claimed_at_on_a_processed_sha_is_not_taken_over(self, db_path: Path) -> None:
        """A finished document is never handed out again even when its claim
        row is a BLOB: the completed-work guard has to survive this failure
        path too, the twin of
        ``test_untrustworthy_claim_on_a_processed_sha_is_not_taken_over``."""
        import sqlite3

        sha = "cf" * 32
        with open_state_db(db_path) as db:
            db.record_processed(_sample_processed(sha=sha))
            db.connection.execute(
                "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
                (sha, sqlite3.Binary(b"\x00\x01")),
            )

            assert db.claim(sha, max_age=timedelta(minutes=60)) is False
            # Same verdict the no-max_age path already gives for a processed sha.
            assert db.claim(sha) is False
            assert db.dedup(sha).is_duplicate is True

    def test_unreadable_claims_table_raises_instead_of_reporting_staleness(self, db_path: Path) -> None:
        """Only an unreadable timestamp is absorbed - not an unreadable database.

        A locked or missing table says nothing about how old a claim is.
        Answering "stale" for it turns any database fault into permission to
        steal a live claim, which is worse than the stack trace the absorbing
        exists to prevent.
        """
        import sqlite3

        sha = "ce" * 32
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            db.connection.execute("DROP TABLE claims")
            with pytest.raises(sqlite3.OperationalError):
                db.is_claim_stale(sha, timedelta(minutes=60))

    @pytest.mark.parametrize("max_age", [3600, 3600.0, "1h"])
    def test_non_timedelta_max_age_raises_instead_of_returning_a_verdict(self, db_path: Path, max_age: object) -> None:
        """Seconds passed where a timedelta belongs is a caller bug, and a bool
        answer hides it. Absorbing that comparison as "stale" would release
        every live claim the caller asked about."""
        sha = "df" * 32
        with open_state_db(db_path) as db:
            assert db.claim(sha) is True
            with pytest.raises(TypeError):
                db.is_claim_stale(sha, max_age, now=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc))


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

    @pytest.mark.parametrize(
        "seeded_claimed_at",
        [(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "not-a-timestamp"],
        ids=["abandoned-an-hour-ago", "unreadable-stamp"],
    )
    def test_only_one_winner_when_workers_race_to_reclaim_a_stale_claim(
        self, db_path: Path, monkeypatch: pytest.MonkeyPatch, seeded_claimed_at: str
    ) -> None:
        """Reclaiming must stay as exclusive as claiming.

        Every worker meets the same abandoned claim, so every worker takes
        the reclaim branch - drop the dead row, then insert its own. A
        reclaim that is not atomic hands one document to several workers.

        A row nobody can parse is abandoned too, and it takes a different
        code path to that verdict. Two workers reading it as untrustworthy
        at the same instant must still leave one winner: the table looks
        healthy afterwards either way (one row, one fresh stamp), so the
        count of winners is the only thing that tells them apart.
        """
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

        worker_count = 5
        sha = "decaf0" * 10 + "beef"  # 64 hex chars
        # Schema and the abandoned claim are seeded in the parent so the
        # children race only the reclaim. Its worker is long gone, well past
        # the one-minute max_age they all pass in.
        seed = StateDB.open(db_path)
        seed.connection.execute(
            "INSERT INTO claims (sha256, claimed_at) VALUES (?, ?)",
            (sha, seeded_claimed_at),
        )
        seed.connection.close()

        ctx = mp.get_context("spawn")
        out_queue: mp.queues.Queue[str] = ctx.Queue()
        barrier = ctx.Barrier(worker_count)
        processes = [
            ctx.Process(
                target=_concurrency_workers.reclaiming_claim_worker,
                args=(str(db_path), sha, 60.0, out_queue, barrier),
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
        assert all(r in ("true", "false") for r in results), f"a worker failed outright: {results}"
        assert results.count("true") == 1, f"expected exactly 1 winning reclaim, got: {results}"
        assert results.count("false") == worker_count - 1, f"expected {worker_count - 1} losers, got: {results}"

        # The stale row was taken over once, not duplicated or wiped.
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

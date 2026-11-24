# Decision Audit Log: 00161-bim-utc-ids-v1

PRD: `00161-bim-utc-ids-v1.md`
Started: 2026-11-24T21:20:31Z
Completed: 2026-11-24T21:20:31Z
Autonomous: 6  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-24T21:20:31Z

**Decision**: design approach for 00161

**Choice**: Build the note once and iterate a fixed candidate list (base, then seconds 60-99) with O_EXCL; Rust mirrors UTC rules and returns None for non-ASCII stems; CACHE_VERSION 5; .so rebuilt locally, never committed.

**Rationale**: Deterministic order, no sleep, no rebuild; open non-blockers logged in the design Review log (lazy candidate paths, utcoffset naive check, Unicode suffix divergence, filename-only suffixed notes, extra collision-test assertions).

### [autonomous] 2026-11-24T21:20:31Z

**Decision**: owner scope change via peer session: Prague rule for naive dates (id_naive_timezone, chrono-tz, cache zone validity)

**Choice**: finish 00161 on current scope; after finalize, write PRD 00165 (00164 taken by intake cea75f91 on feature/merge-klyreon-to-bim) and run it through the full gate

**Rationale**: too large for rework without design; rework_cap 2 risks cap-out

### [autonomous] 2026-11-24T21:20:31Z

**Decision**: `get_creation_datetime.assert_called_once_with(f)` is asserted twice in a row. Remove the second line.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-24T21:20:31Z

**Decision**: `test_create_never_sleeps` asserts `time.monotonic() - started < 0.3` over 40 `exists()` calls. This is a wall-clock bound that can flake on slow CI filesystems. The assumptions file already records Pat's flake warning. The `time.sleep` patches already catch the real regression, so remove the bound or loosen it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-24T21:20:31Z

**Decision**: R17 docs build evidence missing (Bob VERIFY)

**Choice**: routed to verification: uv run sphinx-build -b html docs/source docs/build/html (checks-1.json)

**Rationale**: VERIFY item with exact command; runs in the tail sweep's step-7 pass

### [autonomous] 2026-11-24T21:20:31Z

**Decision**: cycle 1 single-voice medium/low rows R3-R16, R18; mech replay rows R19-R20

**Choice**: discarded to ledger; verified defects R6 (naive parity test), R7 (lexical suffix compare), R8 (None-base and symlink safeguard tests) carried into PRD 00165 scope

**Rationale**: single-voice rule; R19/R20 are replay artifacts (editable install resolves to HEAD); 00165 edits the same files

# bim doc: claim release + dedup identity integrity

<!-- requirements; migrated from PRD 00044 flat file -->

## Problem

Two related correctness holes in the bim doc ingest/dedup machinery:

1. **Ctrl-C parks a document forever.** The ingest claim is released only inside `except Exception` (`src/tools/bim/commands/doc/shared/pipeline.py:178-197`). `KeyboardInterrupt` is a `BaseException`, so it escapes the handler; there is no `finally`, no claim TTL, and no clear command. A user who Ctrl-C's a minutes-long OCR/LLM ingest leaves the claim row in place, and every subsequent re-run of that PDF returns success/"duplicate" (`pipeline.py:171-176`) — the document is never filed and nothing says why.

2. **Triage→promote loses dedup identity.** Triage releases the claim without recording the source (`pipeline.py:627`), and promote records the sha of the OCR'd file only (`promote.py:236-237`), while ingest dedups on the raw staging file's sha (`pipeline.py:155`). So a triaged-then-promoted document that arrives again (re-download / re-export) is not recognized as a duplicate: the full pipeline re-runs and a second archive copy is filed under an incremented name.

## Solution

Release the claim on any exit (`try/finally` or catch `BaseException`), give claims a max age so an abandoned one can be reclaimed, and record the **raw source sha** on the triage/promote path so dedup keys line up across ingest → triage → promote.

## Requirements

### Must have
- Claim release happens on `KeyboardInterrupt`/`SystemExit` as well as normal exceptions (prefer `try/finally` around `_run_after_claim`, keeping the current structured-`CommandResult` mapping for `Exception`).
- Claims already carry a `claimed_at` timestamp (`state_db.py:84`, written but never read today); a claim older than a defined max age (value chosen in the design phase; config-documented; must exceed a slow OCR/LLM ingest ceiling) is treated as stale and reclaimable — a re-run of a parked document proceeds instead of returning "duplicate" forever.
- On triage and on promote, `record_processed` is called for the **raw source** `sha256` (the staging-file sha ingest keys on), not only the OCR'd-file sha.
- Regression tests: (a) simulate `KeyboardInterrupt` during `_run_after_claim` → claim is released, a re-run proceeds; (b) a stale claim is reclaimed after max age; (c) promote records the source sha so a re-ingest of the same source dedups.

### Nice to have
- A small `bim doc claims --clear` (or `--list`) escape hatch for manual recovery.

## Success Criteria

- No interrupt or crash can leave a document permanently unfileable.
- Dedup recognizes a re-arriving source across the triage→promote path.
- bim doc tests green.

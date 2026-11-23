# bim tx: accept UTC note ids and the collision suffix

Status: new. Recorded 2026-11-23.

Source: backlog review of 2026-11-17 on branch `feature/bim-utc-ids`
(`docs/dev/project-management/audit-results/backlog-review-2026-11-17.md`
there), section "Gaps".

## Problem

PRD 00161 (branch `feature/bim-utc-ids`) changes the bim note id rule:

- The id is the UTC digits of `date`, not the local wall clock.
- On a collision the seconds field takes `60` to `99`. `bim create` does not
  sleep. `MAX_ID_ATTEMPTS` and `time.sleep` leave `create_zettel_use_case.py`.

`bim tx` on this branch (PRD 00150) is built on the old rule. When this branch
and 00161 are in one tree, these parts break:

1. `src/tools/bim/commands/tx/shared/validator.py`, `_check_id` (lines
   127-132). The rule `id-created-mismatch` accepts only the digits of `date`
   in its own offset or in the system local zone. A note that `bim tx new`
   makes after 00161 has a local `date` and a UTC id, so `bim tx validate`
   reports every new note. A suffixed id (seconds `60` to `99`) never equals
   the digits of `date` and fails the same rule.
2. `tests/tools/bim/tx/test_validator.py`, class `TestIdCreated`:
   `test_utc_date_matching_local_wall_clock_passes` and
   `test_utc_date_not_matching_local_wall_clock_fails` pin the local rule.
3. `tests/tools/bim/tx/test_new_status.py`,
   `TestNewCollision.test_two_notes_in_one_second_get_different_ids`: it
   patches `create_zettel_use_case.time.sleep` and asserts one-second waits.
   After 00161 there is no `time` import there, so the patch raises
   `AttributeError`, and the second id is a suffix, not the next second.
4. The old tool, `src/tools/klyreon/spec/validator.py:137`, has the same
   id-equals-created rule. PRD 00155 retires klyreon; if it is still alive
   when 00161 lands, it rejects notes with UTC ids too.
5. The tiromex format specification and `docs/source/tools/bim.rst:249` say
   that ids follow local time.

Not affected: `zettel-id-format` (a suffixed id still has 14 digits) and
`id-filename-mismatch`.

## Proposal

- `_check_id` accepts an id that equals the UTC digits of `date`. It also
  accepts seconds `60` to `99` when the first 12 digits equal the UTC digits
  of `date` to the minute.
- Decide whether the old local-time forms stay accepted for notes made before
  the id migration (PRD 00162), or only until that migration runs.
- Rewrite the tests in items 2 and 3 to the new rules.
- Update the format specification and the docs line.

## When

Do this in the merge that first brings this branch and PRD 00161 together,
whichever branch reaches master second. The suite fails at that merge
(item 3) and `bim tx validate` goes wrong without a failing test (item 1).

# muc: report tidy actions through CommandResult, not the logging module

Status: processed, implemented and merged to master as `d02978ca` (PR #274), 2026-11-10. Recorded 2026-11-08.

## Verification (2026-11-15)

- The implementation is present on master and this worktree, not only the
  retired feature branch. All five helpers return actions and recoverable
  warnings; `CommandTidy` aggregates them and the CLI renders literally.
- No Python logging remains in `src/tools/muc/`.
- Existing independent review: `docs/dev/project-management/reviews/muc-tidy-reporting-independent-review.md`.
  Its deferred pre-existing behavior remains outside this intake's scope.
- Fresh verification: the tidy reporting, tidy command, metadata merge,
  console adapter and sysup default-config suites passed together: 93 tests.
  Used the main checkout's existing Python environment with this worktree's
  `src/tools` and `src/lib` on PYTHONPATH; the new worktree environment had
  no pytest installation. No application code changed during this check.
- Moved to processed after verifying completion; no new PRD is needed.

## Problem

AGENTS.md routes all user-facing output through `console` and bans the Python
logging module. muc is the only tool that still uses it: the five
`src/tools/muc/shared/dir_tree/` helpers each create
`logging.getLogger(__name__)`.

- `merge_mac_metadata.py`: `Merged …`, `Deleted …` (info), `Kept …: <error>`
  (warning, added 2026-11-08 with the AppleDouble fix)
- `rename_equivalent_extensions.py`: `Renamed … -> …`
- `lowercase_file_extensions.py`: `Renamed … -> …`
- `delete_by_extension.py`: `Removed extra file …`
- `remove_empty_directories.py`: `Removed empty directory …`

Nothing configures a handler, so:

- every `info` line is dropped. `muc tidy` renames, merges and deletes files and
  then prints only `Tidied <dir>`; the user cannot see what changed.
- the `Kept …` warning reaches stderr through Python's last-resort handler as a
  bare line without a console marker, and is the only sign that a `._` file
  could not be merged.

Several helpers also swallow `OSError` with `pass`, so a failed rename or delete
is invisible.

## Proposal

- Make each `DirTree` helper return what it did (actions and failures) instead
  of logging.
- `CommandTidy.execute` collects them into `CommandResult.info` (actions) and
  `CommandResult.warnings` (kept `._` files, failed renames or deletes), and
  `console.report_result` renders them.
- Drop `import logging` from muc. Keep the existing error policy (a failure
  never aborts the rest of the tidy).

## Decisions

- Report every completed action using the existing console renderer; no new
  verbosity flag or summary mode.
- Recoverable failures remain warnings and do not change exit status 0.
  Catch individual filesystem errors so remaining items and cleanup stages run.
- Keep result messages as plain text for programmatic callers. The CLI selects
  `console.report_result(..., literal=True)` so markup and emoji codes in
  filenames display literally.

# muc: report tidy actions through CommandResult, not the logging module

Status: implemented on `feature/muc-tidy-reporting`, 2026-11-10. Recorded 2026-11-08.

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
- Keep result messages as plain text for programmatic callers; escape Rich
  markup only in the CLI so bracketed filenames display literally.

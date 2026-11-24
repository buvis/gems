# Assumptions ledger: PRD 00162 (bim id migration script)

## 1: Write plan_migration in the bim id migration script

Tess:
- Skip.path, already_utc, local_digit_mismatch and kept_attachments hold absolute paths under the resolved vault.
- Skips and hash values are compared as sets because their order is not specified.
- A MigrationError for a bad notes/ root has "notes" in its message.
- reference_count does not count a reference inside inline code.
- local_digit_mismatch has no fixed order, so the tests compare it sorted.
- A difference only in the seconds between the old id and the date counts as a mismatch.
- "Migrating old id" in the kept_attachments rule leaves out the old ids of skipped notes.
- A note whose frontmatter is not UTF-8 gets REASON_NOT_UTF8 even when its id and date lines are valid ASCII.

Orchestrator: the `Plan.hashes` keys are the absolute paths of the regular `.md` files under the resolved vault/notes. Symlink leaves have no key.

Ivan:
- local_digit_mismatch covers every note whose date resolved, before the shared-stem and suffix steps.
- The shared-stem check applies only to renaming notes. A note already on UTC is never skipped as shared.
- A note already on UTC whose date line changes goes in both changes (with new_id == old_id) and already_utc.
- Plan.skips is sorted by path.
- The skip checks run in this order: type block, type document, non-UTF-8, then date or old id, then shared stem.
- The link-target scan for occupied_stems uses `\[\[([^\[\]|#\n]*)` without a closing `]]`. It can block a few extra ids, which is safe.
- In `_from_old_id`, an OverflowError from a year 1 or 9999 old id is not handled.
- The header imports `argparse`, `json`, `os`, `sys` and `atomic_write_bytes` stay unused until tasks 2 and 3 use them.

## 2: Write apply_migration and undo_migration in the bim id migration script

Tess:
- `outside_references` and the `UndoReport` tuples may hold absolute or vault-relative paths. The tests accept both, and accept the old or the new path of a renamed note.
- An undo that stops on a write error raises MigrationError.
- The map text equals `json.dumps(data, indent=2, sort_keys=True)`. The tests sort `files` by `old_path`.
- A quoted id line keeps its quotes and comment when the id changes.
- A fresh module loaded under a new name stands in for a fresh process in the undo tests.

Orchestrator:
- Task 2 tests are in a sibling file, `test_migrate_ids_apply.py`, so that neither test file passes 800 lines.
- The undo skip fixpoint now checks only skipped files for links to new stems, not unchanged files. This is a design fix, and test commit 32e9db10 covers it.
- Pat's MEDIUM on `_check_record` was rejected: `rec[key] if ok else None` stops checking at the first bad path. Test commit b9319d01 pins this.
- sonnet-run.sh could not authenticate (OAuth expired), so the per-task reviews ran on the native autopilot:pat agent (sonnet).

Ivan:
- The undo reverse map also holds moved entries classified as "unchanged", that is, entries an earlier stopped undo already restored.
- The blocked-chain check applies only to moved entries.
- UndoReport lists restored and unchanged entries by old path, and skipped entries by new path.
- Warnings about links in files outside notes/ go to stderr.
- A MigrationError from undo carries the map file.

## 3: Add the argparse entry point to the bim id migration script

Tess:
- The repo root is `Path(__file__).resolve().parents[5]`. The dispatch said `parents[4]`, which was wrong.
- The dry-run count labels may use any wording. The tests pin each count next to "migrat", "reference" or "UTC".
- The outside-reference check cannot catch a `main` that drops `outside_references`, because `apply_migration` already warns on stderr.

Ivan:
- `--apply` prints only the backup line before it applies, not the dry-run table.
- The zone check sits in the CLI layer, so `plan_migration` with a bad zone still raises ZoneInfoNotFoundError.
- The file was compacted to exactly 800 lines: the blank lines after section headers were removed and a few helpers reflowed (20 hunks). Pat's LOW on this churn is accepted.

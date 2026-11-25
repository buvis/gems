---
design: skip
default_model: sonnet
model_tier_rationale: One guard with exact message text; every check fails loudly.
---
# `bim archive` deletes a note that is already in the archive

Source: agoge run 2026-11-23, finding 1 of 21 (HIGH, verified, lane trudy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

Archiving a note that already sits in the archive directory reports success and deletes the note. Un-archiving a note that already sits in the vault does the same. The command writes the note to its destination and then deletes the source. When both are the same file, the delete removes the only copy.

The web server's `archive` action drives the same command class, so it loses the note too and answers `"success":true`.

A user who repeats an archive command, or runs it on the wrong side, loses the note with a success message. The loss is permanent unless the vault is backed up.

## Solution

`CommandArchiveNote.execute` refuses a path whose destination is the path itself.

For each path, after the existing `is_file` check and before `self.repo.find_by_location`, compute `dest = destination / path.name`. If `dest.resolve() == path.resolve()`, skip the path: no repository call, no `mkdir`, no write, no delete.

The skipped path is recorded like a missing path is today: its message joins `warnings`, and the loop continues. The existing end of `execute` then applies unchanged: when no path was archived, the result is `CommandResult(success=False, error="\n".join(warnings), warnings=warnings)`.

Exact message text, with `{path}` as the path the caller passed:

- archive (no `--undo`): `{path} is already in the archive`
- `--undo`: `{path} is already in the zettelkasten`

Resulting behaviour:

- `bim archive <archive>/note.md` prints ` ✘ <archive>/note.md is already in the archive`, exits 1, and the file is untouched.
- `bim archive --undo <vault>/note.md` prints ` ✘ <vault>/note.md is already in the zettelkasten`, exits 1, and the file is untouched.
- `POST /api/actions/archive` for a note already in the archive answers 422 with `"success": false` and the same error text. No change is needed in `src/tools/bim/commands/serve/_actions.py`: `handle_archive` returns the command's result, and the route maps a failed result to 422.
- In a batch, a refused path beside a valid one is a warning and the valid one is still archived. This matches the missing-path rule.

The write-then-delete order for a real move stays as it is. Making the move atomic is a different option and is out of scope.

## Requirements

### Must have
- `CommandArchiveNote.execute` with one path already in `path_archive` returns `success is False`, `error == f"{path} is already in the archive"`, and never calls `repo.find_by_location`.
- `CommandArchiveNote.execute` with `undo=True` and one path already in `path_zettelkasten` returns `success is False`, `error == f"{path} is already in the zettelkasten"`, and never calls `repo.find_by_location`.
- `bim archive` on a real note file inside the archive directory, with the real repository, exits 1 and the file still exists with the same content.
- A refused path beside a valid path yields `success is True`, `metadata["count"] == 1`, and the refusal text in `warnings`.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **bim**: \`bim archive\` on a note that is already in the archive, and \`bim archive --undo\` on a note that is already in the zettelkasten, now fails with an error and leaves the note in place. Before, both reported success and deleted the note. The web UI's archive action is covered too.`

### Nice to have
- None.

## Implementation

### Module: archive same-file guard
- **Location**: `src/tools/bim/commands/archive_note/archive_note.py`, `tests/tools/bim/test_archive_note.py`, `tests/tools/bim/test_note_write_cli_exit_code.py`, `CHANGELOG.md`
- **Responsibility**: refuse to archive or un-archive a note whose destination is the note itself
- **Exports**: none
- New symbols: `test_refuses_to_archive_a_note_already_in_the_archive`, `test_refuses_to_unarchive_a_note_already_in_the_zettelkasten`, `test_already_archived_note_beside_a_real_one_is_a_warning`, `test_archive_of_note_already_in_the_archive_exits_nonzero_and_keeps_the_file`
- **Risk**: A script that relied on the old "success" for a repeated archive now gets exit 1 (the old run deleted the note, so it was never a safe no-op). The guard compares resolved paths, so a note reached through a symlinked directory is refused too; that is intended. No existing test pins the old behaviour: the four tests in `tests/tools/bim/test_archive_note.py` use a source outside the destination directory and must stay green unchanged.

### Dependencies
- archive same-file guard: No dependencies (foundation)

## Test Strategy

Command-level tests go in `tests/tools/bim/test_archive_note.py`, class `TestCommandArchiveNote`, with the existing `repo_mocks` fixture. Each creates a real file inside the destination directory, runs the command, and asserts the failed result, the exact error text, `repo.find_by_location.assert_not_called()`, and that the file still exists.

The mock repository never deletes a file, so one CLI test uses the real repository to prove the file survives. It goes in `tests/tools/bim/test_note_write_cli_exit_code.py`, class `TestArchiveExitCode`. It writes the `minimal_zettel` fixture text to `tmp_path / "archive" / "20261116120003.md"`, patches only `bim.note_write_cli.get_settings` with `_settings(tmp_path)`, runs `bim archive <that file>`, and asserts exit code 1, `is already in the archive` in the output, and the file content unchanged. On the unmodified code this test fails because the file is gone.

The serve action is covered at the command level: `handle_archive` builds the same `CommandArchiveNote` and returns its result.

Evidence from the report, verbatim:

```
**Evidence** (confirmed). `bim archive <S>/archive/20261116120003.md` -> rc 0,
` ✔ Archived 20261116120003.md`; the archive directory is then empty and the file is nowhere in
the scratch tree. `bim archive --undo <S>/vault/20261116120001.md` -> ` ✔ Unarchived`, vault empty.
`POST /api/actions/archive` with a valid token -> 200 `"success":true`, file gone. Not checked:
whether this predates the range.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_refuses_to_archive_a_note_already_in_the_archive`, `test_refuses_to_unarchive_a_note_already_in_the_zettelkasten` and `test_already_archived_note_beside_a_real_one_is_a_warning` to `tests/tools/bim/test_archive_note.py`, and `test_archive_of_note_already_in_the_archive_exits_nonzero_and_keeps_the_file` to `tests/tools/bim/test_note_write_cli_exit_code.py`; watch them fail - Acceptance: `uv run pytest tests/tools/bim/test_archive_note.py tests/tools/bim/test_note_write_cli_exit_code.py -k "refuses_to or already_archived_note or already_in_the_archive"` fails on the unmodified code.
- [ ] Add the same-file guard to `CommandArchiveNote.execute` with the two exact messages (depends on: previous task) - Acceptance: `uv run pytest tests/tools/bim/test_archive_note.py tests/tools/bim/test_note_write_cli_exit_code.py` passes.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "already in the archive" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/tools/bim/test_archive_note.py tests/tools/bim/test_note_write_cli_exit_code.py` passes; the project's full test gate (`uv run pytest`) passes.

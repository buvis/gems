# Atomic write foundation (note-save data-loss fix)

<!-- requirements; migrated from PRD 00041 flat file -->

## Problem

Every zettel note save is truncate-then-write: `MarkdownZettelRepository.save` calls a bare `Path(data.file_path).write_text(formatted, encoding="utf-8")` at `src/lib/buvis/pybase/zettel/infrastructure/persistence/markdown_zettel_repository/markdown_zettel_repository.py:55`. This is the **single write path for every note mutation** — `bim edit`, create, sync, archive, format, the TUI, and the WebUI PATCH all funnel through `save()` (via `update_zettel_use_case.py:40` and `create_zettel_use_case.py:31`). A crash, kill, or `ENOSPC` mid-write truncates the file: the note's content is gone with no backup. Separately, the updater's shared state file (`src/lib/buvis/pybase/updater/state.py:36-42`) is also a non-atomic `write_text` (it can tear its JSON). The repo already owns the correct pattern at `src/tools/bim/commands/doc/shared/atomic_write.py` (mkstemp in the same dir + fsync + `os.replace` + cleanup) — it is just not where the library can reach it, so this is one of **four divergent atomic-write copies**.

## Solution

Lift the proven atomic-write implementation into the shared library at `src/lib/buvis/pybase/filesystem/atomic_write.py`, then repoint the data-loss-critical write paths (zettel save, updater state) and the existing bim doc callers onto it. This kills the note-save data-loss bug, makes updater state crash-safe, and collapses three of the four copies to one. (pidash's two copies are not repointed at all: 00071 deletes the tool, so they go away with it.)

## Requirements

### Must have
- `atomic_write_text(path, data, *, encoding="utf-8")` and `atomic_write_bytes(path, data)` in `pybase/filesystem/`, exported via `filesystem/__init__.py` `__all__`, using the same-directory tempfile + `fsync` + `os.replace` + on-failure cleanup as the existing `doc/shared/atomic_write.py`.
- `MarkdownZettelRepository.save` uses `atomic_write_text`.
- `updater/state.py._write_state` uses `atomic_write_text` (preserve its existing error-swallowing semantics — a torn cache self-heals, but the write must not leave partial JSON).
- The existing `bim/commands/doc/shared/` callers import from `pybase/filesystem`; the doc-local `atomic_write.py` module is removed (its home is now the library).
- A regression test that a save interrupted before completion leaves the original file intact (simulate by patching `os.replace`/the tempfile write to raise, assert the destination is unchanged).

### Nice to have
- `atomic_write_text` accepts `mode: int = 0o644` so future callers can set 0600 for secrets.

## Success Criteria

- No product code path writes a note or the updater state with a bare `write_text`.
- Interrupted note save is proven non-destructive by test.
- The doc-local `atomic_write.py` is deleted and `pybase.filesystem.atomic_write` is the single canonical implementation (pidash's two copies need no repoint — 00071 removes the tool; 00049/00059 stay parked in `hold/`); `mypy src/lib src/tools` and `pytest` green.

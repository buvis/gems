# Atomic write foundation (note-save data-loss fix)

<!-- tasks; migrated from PRD 00041 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Create `pybase/filesystem/atomic_write.py` by lifting the impl from `doc/shared/atomic_write.py`; export in `filesystem/__init__.py` — Acceptance: `from buvis.pybase.filesystem import atomic_write_text, atomic_write_bytes` works; unit test covers happy-path replace and same-dir tempfile.

### Phase 1: Core
- [ ] Repoint `MarkdownZettelRepository.save` (`:55`) to `atomic_write_text` (depends on: Phase 0) — Acceptance: regression test proves an interrupted save leaves the original note intact.
- [ ] Repoint `updater/state.py._write_state` (`:36-42`) to `atomic_write_text`, keeping error-swallow (depends on: Phase 0) — Acceptance: state write is atomic; existing updater tests pass.
- [ ] Repoint `bim/commands/doc/shared/` callers to `pybase.filesystem`; delete `doc/shared/atomic_write.py` (depends on: Phase 0) — Acceptance: the only `atomic_write` references under `src/tools/bim` import from `buvis.pybase.filesystem`; bim doc tests pass.

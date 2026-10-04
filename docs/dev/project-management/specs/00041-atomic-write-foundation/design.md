# Atomic write foundation (note-save data-loss fix)

<!-- design; migrated from PRD 00041 flat file -->

## Implementation

### Module: pybase.filesystem.atomic_write
- **Location**: `src/lib/buvis/pybase/filesystem/atomic_write.py`
- **Responsibility**: crash-safe file replacement (tempfile in same dir → fsync → `os.replace`).
- **Exports**: `atomic_write_text()`, `atomic_write_bytes()`

### Dependencies
- `pybase.filesystem.atomic_write`: no dependencies (foundation).
- `MarkdownZettelRepository`, `updater.state`, bim doc callers: depend on [`pybase.filesystem.atomic_write`].

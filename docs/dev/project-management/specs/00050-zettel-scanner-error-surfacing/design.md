# zettel scanner: surface parse errors instead of dropping notes

<!-- design; migrated from PRD 00050 flat file -->

## Implementation

### Module: zettel infrastructure repository
- **Location**: `src/lib/buvis/pybase/zettel/infrastructure/persistence/markdown_zettel_repository/markdown_zettel_repository.py`
- **Responsibility**: load notes and report which ones failed, identically across Rust and Python backends.
- **Exports**: `find_all` / query methods (return or surface `errors`); Python fallback loop wrapped to collect errors.

### Dependencies
- No cross-PRD dependency. (Respects the Rust/Python parity contract — see `tests/lib/zettel/parity/`.)

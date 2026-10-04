# Prune the formatting package and relocate suggest_tags

<!-- tasks; migrated from PRD 00061 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Delete the unused formatting methods + orphaned tests; confirm the four live callers still resolve (no deps) — Acceptance: `rg` shows the removed methods have no production caller; tests green.

### Phase 1: Core
- [ ] Move `suggest_tags` into bim; update `import_helpers.py` import; drop the facade method (depends on: Phase 0) — Acceptance: bim tag-suggestion works; `formatting` imports no `console`/`urllib`; `mypy`/`pytest` green.

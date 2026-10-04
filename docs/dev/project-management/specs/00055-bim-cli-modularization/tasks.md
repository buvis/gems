# bim: split the cli.py god registry

<!-- tasks; migrated from PRD 00055 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Extract one command group into its own self-registering module as the pattern (no deps) — Acceptance: the group works identically; `cli.py` shrinks by that group.

### Phase 1: Core
- [ ] Move the remaining groups the same way; root `cli.py` becomes composition-only (depends on: Phase 0) — Acceptance: `cli.py` is well under the 800-line cap; all CLI tests pass.
- [ ] Replace hand-rolled result rendering with `console.report_result` (depends on: Phase 0) — Acceptance: output unchanged; `report_result` has real callers.
- [ ] Split `test_cli.py` per module (depends on: Phase 0) — Acceptance: same coverage, mirrored layout.

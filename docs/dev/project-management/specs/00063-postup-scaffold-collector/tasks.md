# postup A: gem scaffold + deterministic collector

<!-- tasks; migrated from PRD 00063 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: A real gem skeleton with typed contracts.

**Tasks**:
- [ ] Run `scaffold.py --multi-interface postup`; wire console script, wheel package, marker, CI path filter, docs stub (no deps) - Acceptance: `uv run postup --version` works; `pytest -m postup` collects the scaffold test.
- [ ] Implement `PostupSettings` (roots/excludes/out_dir/model, XDG default) (no deps) - Acceptance: env prefix + `--config` override tests pass.
- [ ] Implement `contracts.py` pydantic models with `schema_version` (no deps) - Acceptance: round-trip serialize/validate test; unknown version rejected loudly.

**Exit Criteria**: Package imports cleanly on core-only install; contracts tested.

### Phase 1: Core
**Goal**: Discovery and per-repo signal collection.

**Tasks**:
- [ ] Root-scan discovery with excludes + WARN on bad roots (depends on: Phase 0) - Acceptance: fixture tree test covers nested repos, excludes, unreadable root.
- [ ] `git`/`gh` adapters producing per-repo signals with `errors[]` degradation (depends on: Phase 0) - Acceptance: subprocess-mocked tests cover each signal and each failure mode (gh absent, unauthenticated, non-zero exit).

**Exit Criteria**: A repo's full signal set builds from mocked subprocess output.

### Phase 2: Integration
**Goal**: The end-to-end `postup collect` command.

**Tasks**:
- [ ] `CommandCollect`: parallel per-repo collection, `--no-fetch`, contract writes with rotation + history append via `atomic_write` (depends on: Phase 1) - Acceptance: integration test on fixture repos produces all four files; rotation test proves `data-prev.json` correctness; CLI renders via `console.report_result`.
- [ ] Docs page content, CHANGELOG Added entry, coverage/mypy/ruff pass (depends on: Phase 1) - Acceptance: all gems gates green in CI.

**Exit Criteria**: `postup collect` runs on the real portfolio; Success Metrics hold.

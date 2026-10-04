# pidash: versioned state schema + snapshot layout gate

<!-- tasks; migrated from PRD 00059 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] Add `schema_version` to the state model; handle unknown versions explicitly (no deps) — Acceptance: an unversioned/newer payload yields a clear message, not a silent misparse.
- [ ] Add a contract test pinning the model to representative `state.json` payloads — Acceptance: a deliberate field-shape change breaks the contract test.

### Phase 1: Core
- [ ] Extend Textual snapshot tests to the attention banner and pipeline/progress states; document them as the layout-change gate (depends on: Phase 0) — Acceptance: the new snapshot tests are collected and auto-skipped locally (canonical-env-only per AGENTS.md); the baseline step (`gh workflow run update-snapshots.yml`, run post-batch) is documented alongside the gate; the schema contract test remains the in-session gate.

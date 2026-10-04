# dot TUI: refresh git-secret status so changed secrets show (issue #92)

<!-- tasks; migrated from PRD 00046 flat file -->

## Tasks

### Phase 0: Core
- [ ] Add the guarded `cfg secret hide -m` step at the top of `GitOps.status()`, mirroring `status.py:39-45`; surface hide errors — Acceptance: regression test proves a changed secret shows in TUI status with no prior CLI call, and hide runs before status.

# postup G1: absorbed autopilot data layer (durable hooks + versioned state contract)

<!-- tasks; migrated from PRD 00069 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: Contract and lock primitive, tested.

**Tasks**:
- [ ] `AutopilotState` versioned model + contract tests against representative payloads (no deps) - Acceptance: unversioned/newer payload yields a clear message; a deliberate field-shape change breaks the contract test.
- [ ] `with_state_lock` (flock sidecar) + atomic write plumbing on `pybase.filesystem.atomic_write` (no deps) - Acceptance: concurrent-writer test — two interleaved read-modify-write cycles leave both updates intact.

**Exit Criteria**: Lost-update class provably closed at the primitive level; contract pinned.

### Phase 1: Core
**Goal**: Durable hook scripts.

**Tasks**:
- [ ] Port the five hook scripts; the four state mutators wrap their full RMW in `with_state_lock`; settings writes fsync-before-replace (depends on: Phase 0) - Acceptance: per-hook tests (mocked events) show parity behavior; state mutators verified under the lock; `cleanup_session` verified lock-free per 00049.

**Exit Criteria**: Hook behavior parity + durability, fully tested without live Claude sessions.

### Phase 2: Integration
**Goal**: Lifecycle commands and the shared-contract doc.

**Tasks**:
- [ ] `CommandHooksInstall` (order-preserving incl. non-dict entries, idempotent, supersedes pidash entries) + `CommandHooksStatus` (single render helper) + `hooks` subgroup with `@click.pass_context` (depends on: Phase 1) - Acceptance: install-order regression test; idempotency test; pidash-entry supersession test; status renders once.
- [ ] Shared-contract doc note (schema ownership + `schema_version` bump procedure); docs + CHANGELOG Added entry; PR notes "re-run `postup hooks install` after merge to deploy the durable copies" (depends on: Phase 1) - Acceptance: doc note exists and names the autopilot skill as the writer; gems gates green.

**Exit Criteria**: Success Metrics hold; every 00049/00059 obligation maps to a named test or doc artifact.

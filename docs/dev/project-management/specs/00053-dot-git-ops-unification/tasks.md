# dot: unify the git command layer behind one service

<!-- tasks; migrated from PRD 00053 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: one service with every verb, injected deps, no env mutation.
**Tasks**:
- [ ] Create `dot/git/service.py` from `GitOps`, taking `dotfiles_root` via constructor (drop the `os.environ.setdefault` pattern from the command constructors); include the 00045 rm-safety and 00046 secret-status behavior (no deps) — Acceptance: unit tests exercise each verb with a mocked shell, no `os.environ` writes.
**Exit Criteria**: service is fully double-able and tested in isolation.

### Phase 1: Core
**Goal**: CLI commands stop reimplementing git.
**Tasks**:
- [ ] Rewrite `dot/commands/*` to construct `DotGitService` and return its `CommandResult` (depends on: Phase 0) — Acceptance: CLI behavior unchanged (existing CLI tests pass); no git subprocess string built outside the service.
**Exit Criteria**: `rg "cfg (commit|pull|rm|add)"` finds git commands only inside the service.

### Phase 2: Integration
**Goal**: TUI consumes the service; the duplicate layers are gone.
**Tasks**:
- [ ] Point `dot/tui/screens/*` at `DotGitService`; remove/shrink `tui/git_ops.py` and fold `tui/commands/{browse,secrets}` where they duplicate the service (depends on: Phase 1) — Acceptance: TUI tests pass; no second git implementation remains.
**Exit Criteria**: one git implementation in dot; commit-with-secret-hide and pull-with-submodules exist exactly once.

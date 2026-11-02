# Decision Audit Log: 00107-backup-per-instance-excludes-v1

PRD: `00107-backup-per-instance-excludes-v1.md`
Started: 2026-11-02T09:18:41Z
Completed: 2026-11-02T09:18:41Z
Autonomous: 4  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-02T09:18:41Z

**Decision**: Fast-track source combines build and completion review

**Choice**: Preserve card test-author/Ivan work; hand off with tasks_done to fresh provider-routed Alice/Blake/Bob review

**Rationale**: Operator host contract requires fresh work/review boundary for every lane; native sonnet gpt-6.1-sol/medium has independent Anthropic route

### [autonomous] 2026-11-02T09:18:41Z

**Decision**: Attended recovery of held 00107: completion review never ran

**Choice**: Restored preserved build-state snapshot (work base 4becb45e, task provenance unchanged), moved PRD hold->wip, phase-done tasks_done, fresh review-once session

**Rationale**: Handoff 202610292344-review-20261102 authorizes recovery; suite blocker was environment-only and resolved by unchanged 00111 isolation runner

### [autonomous] 2026-11-02T09:18:41Z

**Decision**: `--show-excludes` print order silently changed from sorted to config order; PRD names only the header change, matching is set-based, and no test pins either order (new test uses substring membership)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T09:18:41Z

**Decision**: Test slop in new file: in-body `from backup.config import effective_excludes` beside header imports from the same module; `tuple()` wraps on fields that are already tuples; `assert cfg.excludes == tuple(base)` asserts a frozen model's tuple did not mutate and cannot fail

**Choice**: auto-fixed

**Rationale**: fixed by review-close

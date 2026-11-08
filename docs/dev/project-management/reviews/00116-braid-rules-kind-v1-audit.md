# Decision Audit Log: 00116-braid-rules-kind-v1

PRD: `00116-braid-rules-kind-v1.md`
Started: 2026-11-06T22:19:40Z
Completed: 2026-11-06T22:19:40Z
Autonomous: 5  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-06T22:19:40Z

**Decision**: 00116 design approach

**Choice**: new domain/rules.py reusing engine link helpers via one function-local import; _Projection gains entry_suffix/file_links; generated files via atomic_write_bytes; union stale removal after directory-host removal; Windows hard-link ownership limited to links this run detached; sync_rules keeps the PRD 6-arg signature with a per-file PLR0913 ignore; test builders in helpers.py

**Rationale**: design-solution 3 dispatches, 10 blockers fixed, 0 open; open non-blockers: adoption MISMATCH STATE once, host-root removal state drift once, render re-reads RULE.md, orphan miss via retiring union entry, dangling Windows junction cleanup is a shared 00115 engine follow-up

### [autonomous] 2026-11-06T22:19:40Z

**Decision**: Windows regeneration claims a foreign instruction file: sync once, replace the recorded host link with a regular file, then change a rule. `host in regenerated` makes that foreign file owned, so braid backs it up and replaces it instead of reporting UNMANAGED. Capture recorded links that pass `samefile` before generation; permit hard-link replacement only for those hosts. Add this regression test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-06T22:19:40Z

**Decision**: `sync_rules` takes `emit` keyword-only (`*, emit`), but the PRD and design give the verbatim contract `sync_rules(settings, inventory, ignored, previous, result, emit)`. A positional call raises TypeError. Drop the `*,` so the exported signature matches. `engine.run` and the tests only pass `emit=` as a keyword, so nothing else changes.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-06T22:19:40Z

**Decision**: 00116 cycle 1 decision gate: 15 findings

**Choice**: R1 (Windows foreign-file ownership on regeneration, high) and R2 (keyword-only emit, 2/4) -> fix task 6 at opus; R3-R15 single-voice medium/low -> discarded to ledger

**Rationale**: R1 verified in rules.py:297: host in regenerated grants ownership to any recorded regular file on nt; single-voice M/L discard rule; cycle 1 < cap 2

### [autonomous] 2026-11-06T22:19:40Z

**Decision**: cycle 2: 3 single-voice Low findings (R1-R3)

**Choice**: discard; no tail sweep

**Rationale**: single-voice Lows; review converged with no CRITICAL/HIGH

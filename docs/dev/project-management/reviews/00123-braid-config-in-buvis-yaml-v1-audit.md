# Decision Audit Log: 00123-braid-config-in-buvis-yaml-v1

PRD: `00123-braid-config-in-buvis-yaml-v1.md`
Started: 2026-11-10T12:59:28Z
Completed: 2026-11-10T12:59:28Z
Autonomous: 12  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R1 test_no_sources_is_refused_without_reading_the_old_sources_d sets up legacy sources.d/env that resolve_settings never reads (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R2 _expand_configured re-expands paths that _deduplicate/_resolved expand again; only its absoluteness check is load-bearing (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R3 malformed list-typed sources:/policies: YAML surfaces an uncaught ConfigurationError traceback with exit 1 (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R4 .braidignore source list does not state policies entries must be absolute or start with ~ (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R5 PRD task 4 / Phase 1 acceptance greps are self-contradictory; build followed the Contract text (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]; PRD self-contradiction, implementation choice correct

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R6 doc markup and wrap drift around buvis-braid.yaml mentions (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R7 YAML policies and --policy never tested combined at the CLI layer (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R8 PRD acceptance rg clauses cannot pass as written against mandated migration text and negative test names (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]; PRD self-contradiction

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R9 BUVIS_BRAID_SOURCES/POLICIES env overrides exist but are undocumented in the Configuration table (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R10 migration drops ~/.config/braid/.braidignore with no warning when that directory exists (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]; PRD accepts the no-fallback risk

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R11 relative-YAML-entry error case has no CLI-level test asserting exit 2 and an empty agents root (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]

### [autonomous] 2026-11-10T12:59:28Z

**Decision**: R12 PRD zero-match removal checks conflict with retained migration text and required negative tests (cycle 1)

**Choice**: discarded

**Rationale**: single-voice [1/4]; PRD self-contradiction

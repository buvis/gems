# Count configured Claude-tooling repos as meta in postup's meta-budget

<!-- tasks; migrated from PRD 00087 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: the collector can classify against multiple meta roots.

**Tasks**:
- [ ] Extend `collect` with `meta_repos` and `_is_meta_sid` to match a set of
  encoded prefixes — Acceptance: unit tests cover (a) a session under a
  configured meta-repo → meta, (b) a session under `~/.claude` → still meta,
  (c) a session under an UNLISTED repo → product, (d) empty `meta_repos`
  reproduces exact 00072 behavior, (e) a configured repo path containing a `.`
  (e.g. a `github.com` path) encodes and matches correctly. All fixtures use
  `tmp_path` + override roots, never the real home.

**Exit Criteria**: collector green; empty-list default byte-identical to 00072.

### Phase 1: Core
**Goal**: the configured set reaches both brief surfaces.

**Tasks**:
- [ ] Add `PostupSettings.meta_repos: list[str]` and pass it (expanded to
  absolute Paths) from both `collect.py` and `brief.py` — Acceptance: a test
  seeds `meta_repos` through settings and asserts the attributed meta share
  includes the configured repo; CHANGELOG updated in the same commit.

**Exit Criteria**: Success Metrics all verifiably true; live probe with the
three repos configured shows meta rising above the `~/.claude`-only figure.

### Phase 2: Integration
**Goal**: none — retained for template parity.

**Tasks**: none — this PRD completes in two phases.

**Exit Criteria**: n/a — see Phase 1.

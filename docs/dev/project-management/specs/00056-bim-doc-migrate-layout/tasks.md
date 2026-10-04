# bim doc migrate-layout: ship the promised legacy-zettel migration

<!-- tasks; migrated from PRD 00056 flat file -->

## Tasks

### Phase 0: Foundation
- [ ] `CommandMigrateLayout` computing the migration plan from the legacy list (dry-run) (depends on: 00041) — Acceptance: dry-run prints planned moves, changes nothing on disk.

### Phase 1: Core
- [ ] Apply path: atomic move + v1 frontmatter rewrite via shared writers; skip-and-report divergent files (depends on: Phase 0) — Acceptance: fixture migrates; divergent fixture skipped; post-migration audit shows them gone; frontmatter link valid.
- [ ] Wire `bim doc migrate-layout` into `cli.py`; update `bim.rst` + README (depends on: Phase 0) — Acceptance: `--help` shows it; docs describe dry-run default.

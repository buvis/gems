# bim doc migrate-layout: ship the promised legacy-zettel migration

<!-- design; migrated from PRD 00056 flat file -->

## Implementation

### Module: bim.commands.doc.migrate
- **Location**: `src/tools/bim/commands/doc/migrate/` (new command group, lazy-imported in `cli.py` per convention)
- **Responsibility**: move + rewrite legacy-layout zettels to v1, safely and reversibly-by-dry-run.
- **Exports**: `CommandMigrateLayout`

### Dependencies
- Depends on [00041] (atomic rewrite). Reuses `commands/doc/shared/` writers/validators. No dependency on a higher-numbered PRD.

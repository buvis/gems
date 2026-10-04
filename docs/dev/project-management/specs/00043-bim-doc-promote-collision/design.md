# bim doc promote: stop overwriting on canonical-name collision

<!-- design; migrated from PRD 00043 flat file -->

## Implementation

### Module: bim.commands.doc.promote
- **Location**: `src/tools/bim/commands/doc/promote/promote.py`
- **Responsibility**: finish a triage proposal into a filed PDF + zettel **without** clobbering an existing file.
- **Exports**: `CommandPromote` (behavior change in `_finalize`/name planning)

### Dependencies
- Reuses the collision resolver from `shared/pipeline.py:722-758` (extract to `shared/naming.py` or `shared/` if needed for sharing). No cross-PRD dependency.

# Delete dead code: uv adapter, hello_world, configuration/examples

<!-- design; migrated from PRD 00060 flat file -->

## Implementation

### Module: (deletions)
- **Location**: `src/lib/buvis/pybase/adapters/uv/`, `src/tools/hello_world/`, `src/lib/buvis/pybase/configuration/examples/` (+ tests, docs, pyproject, README)
- **Responsibility**: n/a (removal)
- **Exports**: n/a

### Dependencies
- No dependency. (scaffold.py remains the sole tool template — verify it doesn't reference hello_world.)

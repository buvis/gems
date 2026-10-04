# updater: fail loud on re-exec failure and slow upgrades

<!-- design; migrated from PRD 00047 flat file -->

## Implementation

### Module: pybase.updater.executor
- **Location**: `src/lib/buvis/pybase/updater/executor.py`
- **Responsibility**: perform the upgrade + re-exec, failing loudly and never masking the user's command.
- **Exports**: `run_update()` / re-exec path (exit non-zero + console message on failure; no 120s kill)

### Dependencies
- No dependencies.

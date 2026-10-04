# pidash hooks: lock, fsync, and preserve order

<!-- design; migrated from PRD 00049 flat file -->

## Implementation

### Module: pidash.hooks + pidash.commands.hooks
- **Location**: `src/tools/pidash/hooks/*.py`, `src/tools/pidash/commands/hooks/settings.py` / `install.py`
- **Responsibility**: durable, serialized, order-preserving state and settings writes from concurrent hook processes.
- **Exports**: a `with_state_lock(...)` context manager (flock); `save_settings` (fsync); `install` (stable ordering)

### Dependencies
- Depends on [00041] for the shared `atomic_write` helper (repoint pidash's two copies onto it here).

# dot rm: untrack (not destroy) secrets, and quote the filename

<!-- design; migrated from PRD 00045 flat file -->

## Implementation

### Module: dot.commands.rm
- **Location**: `src/tools/dot/commands/rm/rm.py`
- **Responsibility**: untrack a dotfile (plain or secret) without destroying it.
- **Exports**: `CommandRm` (`_remove_encrypted` no longer unlinks plaintext / no longer passes `-c`; both commands quote `file_path`)

### Dependencies
- No dependencies. Single file plus its test. (This is untangled again by 00053's shared git-ops service, but ships the fix now.)

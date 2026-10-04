# dot: make shell quoting actually hold end to end

<!-- design; migrated from PRD 00078 flat file -->

## Implementation

### Module: pybase.adapters.shell
- **Location**: `src/lib/buvis/pybase/adapters/shell/shell.py`
- **Responsibility**: run a shell command without silently un-quoting its
  arguments.
- **Exports**: `ShellAdapter` (`exe` drops the whole-command `expandvars`;
  `_expand_alias` expands vars in the alias body it substitutes)

### Module: dot.commands.delete
- **Location**: `src/tools/dot/commands/delete/delete.py`
- **Responsibility**: remove a dotfile from disk, safely quoting its name.
- **Exports**: `CommandDelete` (both branches quote `file_path`)

### Dependencies
- None. Touches the shared library, so every tool that uses `ShellAdapter` is in
  the blast radius — that is why this is its own PRD rather than part of 00045.

## Provenance

Split out of PRD 00045 at its cycle-1 review gate (2026-08-16). Findings raised
by Blake (blind lens) and Alice; confirmed against `shell.py` and the installed
git-secret 0.5.0 during that review. Deferral reasoning is recorded in
`dev/local/reviews/00045-dot-rm-safety-v1-ledger.json`.

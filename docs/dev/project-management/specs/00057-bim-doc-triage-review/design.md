# bim doc triage: list-and-approve review surface

<!-- design; migrated from PRD 00057 flat file -->

## Implementation

### Module: bim.commands.doc.triage
- **Location**: `src/tools/bim/commands/doc/triage/` (new group; lazy-imported in `cli.py`)
- **Responsibility**: enumerate and approve triage proposals across CLI and (via the seam) the WebUI.
- **Exports**: `CommandTriageList`, `CommandTriageApprove`

### Dependencies
- Depends on the seam contract `dev/local/specs/all-interface-architecture.md` (register as a serve action via the seam). Benefits from [00043] (collision-safe promote) and [00044] (dedup identity). No dependency on a higher-numbered PRD.

# updater: fail loud on re-exec failure and slow upgrades

<!-- tasks; migrated from PRD 00047 flat file -->

## Tasks

### Phase 0: Core
- [ ] Replace the silent `sys.exit(0)` on re-exec failure with a console error + non-zero exit (or in-process fallthrough) — Acceptance: patched failing re-exec → non-zero exit + message; test covers it.
- [ ] Remove/raise the 120s upgrade timeout on the interactive path — Acceptance: a slow (mocked long-running) upgrade is not killed; existing updater tests pass.

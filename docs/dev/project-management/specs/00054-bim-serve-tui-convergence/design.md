# bim: route every interface through the command classes

<!-- design; migrated from PRD 00054 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/bim/commands/serve/
├── _routes.py     # PATCH delegates to use case; action route maps status
├── _actions.py    # handlers return CommandResult.to_dict()
├── frontend/src/lib/api.ts + ActionBar.svelte   # check the envelope
src/tools/bim/tui/
├── create_note.py # routes through CommandCreateNote
└── edit_note.py   # _save surfaces CommandResult failures
```

### Module: bim.commands.serve + bim.tui
- **Maps to capability**: Single write path + Uniform result reporting
- **Responsibility**: thin adapters over the command classes, honoring the seam contract (`dev/local/specs/all-interface-architecture.md`).
- **Exports**: route handlers, TUI screen `_save`/`_create` (behavior change)

## Dependency Graph

### Foundation Layer (Phase 0)
- **result mapping**: follows the per-transport contract in `dev/local/specs/all-interface-architecture.md` (must exist before this PRD starts).

### Core Layer (Phase 1)
- **serve routes/actions**: Depend on [the seam spec] — inline PATCH removed, envelope returned, status mapped.

### Integration Layer (Phase 2)
- **WebUI + TUI**: Depend on [Core] — envelope checked; failures surfaced.

## Test Strategy

### Critical Scenarios
- **Happy path**: create/patch/archive via WebUI and TUI → same result as CLI.
- **Edge case**: TUI create with an empty required answer → rejected (matches CLI).
- **Error case**: a failing delete → WebUI shows error, TUI notifies error, API returns non-2xx.

## Risks

- **Frontend change surface**: `api.ts`/`ActionBar` are SvelteKit with no test harness; keep the envelope check minimal and typed; verified indirectly via route tests, manual smoke post-merge.
- **00042 regression**: 00042 lands confinement/auth on these same routes and the token header in `api.ts` first — this PRD must not drop `confine_path`, the token check, or the `X-Buvis-Token` header when rewriting them.
- **Depends on the seam spec**: do not start before `dev/local/specs/all-interface-architecture.md` exists.

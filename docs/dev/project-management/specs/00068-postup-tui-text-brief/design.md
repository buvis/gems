# postup F: TUI + text brief (Python derive layer)

<!-- design; migrated from PRD 00068 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/
├── domain/
│   └── derive.py            # Maps to: derive module
├── commands/
│   ├── brief/brief.py       # Maps to: brief command (CommandBrief)
│   └── tui/tui.py           # Maps to: tui command (CommandTui)
├── adapters/
│   ├── cli.py               # + default-command dispatch, brief/tui subcommands
│   └── tui/                 # Textual app (screens/widgets)
tests/tools/postup/          # derive/brief tests + snapshot tests
```

### Module: postup.domain.derive
- **Maps to capability**: Python derive layer
- **Responsibility**: Deterministic view-model; UI-free (no Textual/Click imports).
- **Exports**:
  - `load_view_model(out_dir)` - contracts → view-model (incl. missing-data states)
  - `AttentionItem`, `Todo`, `RepoSummary`, `SinceLast` - typed view-model

### Module: postup.commands.brief / postup.commands.tui
- **Maps to capability**: Text brief + Textual TUI
- **Responsibility**: Orchestrate load → render for each surface; return `CommandResult`.
- **Exports**:
  - `CommandBrief` - `execute() -> CommandResult`
  - `CommandTui` - `execute() -> CommandResult`

### Module: postup.adapters.tui
- **Maps to capability**: Textual TUI
- **Responsibility**: Textual app/widgets only; consumes the view-model, computes nothing.
- **Exports**:
  - `PostupApp` - Textual application

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00063 (contracts, CLI group) and 00065 (shared fixture payloads) must be in `done/`.

- **domain.derive**: no internal dependencies — built first.

### Core Layer (Phase 1)
- **commands.brief + default-command dispatch**: depends on [domain.derive]

### Integration Layer (Phase 2)
- **adapters.tui + commands.tui + `postup` extra**: depends on [domain.derive]

## Test Strategy

### Critical Scenarios
- **Happy path**: enriched fixtures → Expected: text brief shows attention/todos/repos/diff; TUI snapshot matches baseline.
- **Edge case**: no `epics.json` / first run without prev → Expected: deterministic subset with "not enriched" cue; no diff section; both surfaces consistent.
- **Error case**: no `data.json` / `postup tui` without the extra → Expected: friendly "run postup collect first" result / `require_import` guidance; never a traceback.

## Risks

- **Textual import leaking onto the default path** (would slow bare `postup` and break core-only installs): enforced by an explicit import-isolation test, not convention.
- **JS/Python derive divergence**: both suites run the same fixture payloads; a semantic change must land in both or a fixture test fails.
- **Snapshot-baseline friction**: baselines only from the canonical env via `gh workflow run update-snapshots.yml` (AGENTS.md); do not hand-bless local SVGs.
- **pidash muscle memory** (bare `pidash` opened a TUI): accepted UX change from review F6 — text brief is the default, TUI is one word away.

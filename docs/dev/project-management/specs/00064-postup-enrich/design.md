# postup B: LLM enrichment via claude CLI

<!-- design; migrated from PRD 00064 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/
├── adapters/
│   ├── cli.py               # + enrich subcommand
│   └── claude.py            # Maps to: Claude CLI adapter
├── commands/
│   └── enrich/enrich.py     # Maps to: enrich command (CommandEnrich)
└── domain/
    ├── epics.py             # Maps to: Epics schema
    └── prompt.py            # Maps to: Prompt ownership
tests/tools/postup/          # adapter/command/schema tests
```

### Module: postup.adapters.claude
- **Maps to capability**: Claude CLI adapter
- **Responsibility**: Detect and invoke the `claude` CLI; no business logic.
- **Exports**:
  - `ClaudeAdapter.is_available()` - presence check
  - `ClaudeAdapter.prompt(text, model, timeout)` - raw response

### Module: postup.domain.epics / postup.domain.prompt
- **Maps to capability**: Enrichment pipeline
- **Responsibility**: The `epics.json` contract and the prompt/rules text; pure, UI-free.
- **Exports**:
  - `EpicsPayload` (+ `JudgmentTodo`, stable ids) - schema
  - `build_prompt(data, digest)` - prompt assembly with size guard

### Module: postup.commands.enrich
- **Maps to capability**: Enrichment pipeline
- **Responsibility**: Orchestrate detect → alert → invoke → validate → retry-once → write/degrade; return `CommandResult`.
- **Exports**:
  - `CommandEnrich` - `execute() -> CommandResult`

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00063 (contracts, settings, CLI group) must be in `done/`.

- **domain.epics + domain.prompt**: no internal dependencies — built first.

### Core Layer (Phase 1)
- **adapters.claude**: depends on [settings (model)]

### Integration Layer (Phase 2)
- **commands.enrich + CLI wiring**: depends on [domain.epics, domain.prompt, adapters.claude]

## Test Strategy

### Critical Scenarios
- **Happy path**: mocked `claude` returns valid JSON → Expected: validated `epics.json` written atomically; INFO alert names the mode/model.
- **Edge case**: first response invalid, retry returns valid → Expected: success with exactly two invocations.
- **Error case**: both attempts invalid / `claude` missing / `data.json` absent → Expected: WARN + deterministic continue (no partial file) / failure `CommandResult` with actionable message; never a traceback.

## Risks

- **Open decision (design): model default** — pin a specific model vs inherit the CLI's default when `PostupSettings.model` is unset; current text assumes inherit-CLI-default.
- **Open decision (design): digest size strategy** — chunk the prompt vs cap commits per repo for large portfolios; `build_prompt`'s size guard implements whichever design picks.
- **`claude -p` fragility (latency, quota, format drift)**: retry-once + loud degradation; enrichment never blocks the deterministic brief.
- **Stable todo ids across runs**: id rule must be deterministic (content-derived), or done-state (00065/00067) breaks — covered by a regression test.

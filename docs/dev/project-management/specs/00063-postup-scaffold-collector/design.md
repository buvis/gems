# postup A: gem scaffold + deterministic collector

<!-- design; migrated from PRD 00063 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/
├── __init__.py
├── __main__.py
├── manifest.toml            # interfaces: cli/tui/rest/web
├── settings.py              # Maps to: Postup settings
├── adapters/
│   ├── __init__.py
│   ├── cli.py               # Maps to: collect command (Click group, entry point)
│   ├── gitrepo.py           # Maps to: collect command (git CLI delegation)
│   └── gh.py                # Maps to: collect command (gh CLI delegation)
├── commands/
│   ├── __init__.py
│   └── collect/collect.py   # Maps to: collect command (CommandCollect)
├── params/
│   └── __init__.py
└── domain/
    ├── __init__.py
    ├── discovery.py         # Maps to: Root-scan discovery
    └── contracts.py         # Maps to: Versioned file contracts
tests/tools/postup/          # mirrors the above
docs/source/tools/postup.rst
```

(Exact file split inside `commands/`/`domain/` may be refined by design-solution; module boundaries below are the contract.)

### Module: postup.settings
- **Maps to capability**: Gem scaffold and wiring
- **Responsibility**: Validated settings with env/config/CLI layering.
- **Exports**:
  - `PostupSettings` - roots/excludes/out_dir/model

### Module: postup.domain
- **Maps to capability**: Repo discovery + Deterministic collection (contracts)
- **Responsibility**: Pure logic: repo scan, typed data model, rotation/append rules. No UI framework imports (library-agnostic seam per AGENTS.md).
- **Exports**:
  - `discover_repos(settings)` - repo path list
  - `PortfolioData` (+ per-repo models, `schema_version`) - the `data.json` contract
  - `write_outputs(...)` - atomic write + rotation + history append

### Module: postup.adapters
- **Maps to capability**: Deterministic collection
- **Responsibility**: All subprocess delegation (`git`, `gh`) and the Click CLI adapter.
- **Exports**:
  - `cli` - Click group (`postup collect`, `buvis_options`)
  - `GitRepoAdapter` / `GhAdapter` - per-repo signal fetchers

### Module: postup.commands.collect
- **Maps to capability**: Deterministic collection
- **Responsibility**: Orchestrate discovery → parallel per-repo collection → contract writes; return `CommandResult`.
- **Exports**:
  - `CommandCollect` - `execute() -> CommandResult`

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00041 (`pybase.filesystem.atomic_write`) must be in `done/`.

- **postup scaffold + settings + domain.contracts**: no internal dependencies — built first.

### Core Layer (Phase 1)
- **postup.domain.discovery**: depends on [settings]
- **postup.adapters (gitrepo, gh)**: depends on [domain.contracts]

### Integration Layer (Phase 2)
- **postup.commands.collect + adapters.cli**: depends on [discovery, adapters, contracts]

## Test Strategy

### Critical Scenarios
- **Happy path**: two fixture repos, mocked git/gh → Expected: valid `data.json` (schema_version set), digest, rotation, history line appended.
- **Edge case**: `--no-fetch` skips remote refresh; one repo path excluded; one root missing → Expected: outputs still written, WARN emitted, excluded repo absent.
- **Error case**: `gh` not authenticated for one repo → Expected: that repo carries `errors[]`, run exits successfully, console WARNs; no traceback reaches the user.

## Risks

- **`gh` rate limits / API flakiness on large portfolios**: carried-over mitigation — per-repo `errors[]`, WARN surfacing, `--no-fetch` fast path.
- **Parallelism flakiness**: bound the worker pool; every worker exception is captured into that repo's `errors[]`.
- **00041 not landed when this PRD starts**: hard blocker — the atomic-write invariant (AGENTS.md) forbids bare writes; do not inline a private copy.
- **Contract churn from later PRDs (enrich/web/TUI)**: `schema_version` exists from day one; additive changes preferred, bumps loud.

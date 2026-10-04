# klyreon D: autonomous maintenance, report-only pruning, scheduler

<!-- design; migrated from PRD 00077 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/klyreon/
├── maintain/
│   ├── __init__.py
│   ├── sweep.py             # Maps to: maintain command (orchestration)
│   ├── rules.py             # Maps to: Lifecycle promotion, Assent transitions
│   ├── moc_sync.py          # Maps to: MOC membership sync
│   ├── prune.py             # Maps to: Prune-candidate detection, Opt-in deletion
│   └── graph.py             # Maps to: corroboration and inbound-link counting
├── schedule/
│   ├── __init__.py
│   ├── launchd.py           # Maps to: schedule install/status/uninstall (macOS)
│   ├── cron.py              # Maps to: schedule install/status/uninstall (Linux)
│   └── installer.py         # Maps to: platform dispatch + manifest recording
└── commands/
    ├── maintain.py          # Maps to: maintain command
    ├── schedule.py          # Maps to: schedule install/status/uninstall
    ├── init.py              # extended: init offers the schedule
    └── status.py            # extended: prune candidates + maintenance freshness
tests/tools/klyreon/maintain/  # + fixtures/backdated, fixtures/promotable
tests/tools/klyreon/schedule/
docs/source/tools/klyreon.rst  # gains maintain + schedule sections
```

### Module: klyreon.maintain.graph
- **Maps to capability**: Maintenance sweep + Pruning
- **Responsibility**: Build the derived views every rule needs: inbound links per zettel, corroborating sources per zettel, open disagreements per zettel. Pure, built once per sweep.
- **Exports**:
  - `VaultGraph.build(root)` - one pass over the vault
  - `inbound(path)` / `corroborating_sources(path)` / `open_disagreements(path)`

### Module: klyreon.maintain.rules
- **Maps to capability**: Lifecycle promotion + Assent transitions
- **Responsibility**: Pure functions from a zettel plus the graph to a planned transition. No I/O.
- **Exports**:
  - `plan_lifecycle(zettel, graph)` / `plan_assent(zettel, graph)` - `Transition | None`

### Module: klyreon.maintain.moc_sync
- **Maps to capability**: Maintenance sweep
- **Responsibility**: Reconcile each MOC's marked member block against the graph. Rewrites only the block.
- **Exports**:
  - `plan_moc_sync(graph)` - per-MOC additions and removals, empty when nothing drifted
  - `apply_moc_sync(root, plan)` - rewrite the block and commit, one commit per MOC

### Module: klyreon.maintain.prune
- **Maps to capability**: Pruning
- **Responsibility**: Candidate detection and the grouped delete-plus-cleanup.
- **Exports**:
  - `find_candidates(graph, window_days)` - candidate list with the reason
  - `prune(root, candidate, graph)` - delete, clean inbound refs and MOC membership, one commit

### Module: klyreon.schedule
- **Maps to capability**: Scheduler
- **Responsibility**: Write, inspect, and remove the platform scheduler artifact, and record it in PRD C's manifest.
- **Exports**:
  - `install(at, binary, path_env)` / `status()` / `uninstall()` - platform-dispatched
  - `render_plist(...)` / `render_cron_line(...)` - pure renderers, unit-testable off-platform

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00074, 00075, and 00076 must all be in `done/`.

- **klyreon.maintain.graph**: depends only on 00074's spec engine.
- **klyreon.schedule.launchd / cron renderers**: no internal dependencies.

### Core Layer (Phase 1)
- **klyreon.maintain.rules**: depends on [maintain.graph]
- **klyreon.maintain.moc_sync**: depends on [maintain.graph, 00074 spec.writer, 00074 vault.git]
- **klyreon.maintain.prune**: depends on [maintain.graph, 00074 vault.git]
- **klyreon.schedule.installer**: depends on [schedule renderers, 00076 assets.manifest]

### Integration Layer (Phase 2)
- **klyreon.maintain.sweep + commands.maintain**: depends on [rules, moc_sync, prune, 00074 spec.validator, 00075 run.lock, 00075 run.trail]
- **klyreon.commands.schedule**: depends on [schedule.installer]
- **klyreon.commands.init / status** (extended): depends on [schedule.installer, maintain.prune]

## Test Strategy

### Critical Scenarios
- **Happy path**: fixture vault with one promotable and one corroborated zettel → Expected: one lifecycle transition, one assent transition, `processed` unchanged on both, one trail, one commit per zettel.
- **Idempotence**: run maintain twice → Expected: the second run reports no transitions and writes only its trail.
- **Pruning off**: backdated orphan fixtures, default settings → Expected: nothing deleted, exact candidate list in the trail and in `status`.
- **Pruning on**: same fixtures, `pruning_enabled: true` → Expected: files deleted, inbound `links`, `doubts[].target`, and MOC membership cleaned in the same commit, vault validates clean.
- **Edge case**: a zettel with two corroborations from the same source document → Expected: assent stays `tentative`.
- **Edge case**: one zettel gains a `mocs` anchor by hand and another drops one → Expected: the sweep adds the first and removes the second inside the marker block, leaves surrounding prose byte-identical, and the re-run plans nothing.
- **Error case**: sweep killed after three of seven commits → Expected: `validate` clean, three transitions committed, re-run applies the remaining four.
- **Error case**: `launchctl bootstrap` fails → Expected: `CommandResult(success=False)` naming the manual command; no manifest entry recorded for an artifact that is not loaded.

## Risks

- **A rule promotes something it should not**: every transition is one commit under the klyreon identity, so `git log --author` shows exactly what the machine did and a revert is one command. The rules are deliberately mechanical and the untestable half of spec 7.3's promotion wording is dropped rather than guessed at.
- **Noise accumulates because pruning is off by default**: accepted in discovery Q19. The candidate count appears in `status` on every check, so the backlog stays visible.
- **Scheduler traps: PATH, launchd label collisions, cron quoting**: an explicit `PATH` and an absolute binary path go into both artifacts at install time, the label is namespaced `net.buvis.klyreon`, and both renderers are unit-tested off-platform. `schedule status` reports the loaded state rather than assuming install worked.
- **Trail files accumulate forever**: one per run, small, git-tracked. No retention rule in v1, matching PRD B. Revisit when a real vault makes the directory unpleasant.
- **A vault the owner edits during a scheduled run**: the vault lock only guards klyreon against itself. Scoped commits mean klyreon never stages a human's edit, and the human's changes to a zettel klyreon is rewriting are the one genuine race, bounded by the per-zettel write window.

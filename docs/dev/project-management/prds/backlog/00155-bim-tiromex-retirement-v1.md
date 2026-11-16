---
design: run
default_model: opus
model_tier_rationale: equivalence evidence across the complete port inventory and source retirement
eligibility: test -f docs/dev/project-management/prds/done/00154-bim-tiromex-maintenance-v1.md
---

# Retire klyreon after the bim tx port

Source: [Discovery 00149](docs/dev/project-management/intake/processed/00149-merge-klyreon-into-bim/discovery.md); adjacent port-plan.md supplies the approved inventory. Discovery overrides older examples. Part 6 of 6; explicit discovery numbering is retained.
External boundary: this card completes repository retirement and prepares host cleanup; it does not claim M31's host-side deletion is complete merely because the code is gone.
Grounding: retirement wiring is at `pyproject.toml:49`, `pyproject.toml:90`, `pyproject.toml:118`; active docs references are at `docs/source/tools.rst:47` and `docs/source/tools.rst:130`.

## Overview

### Problem Statement
Remove the obsolete tool only after all approved inventory rows and consumers have evidence of replacement or authorized drop. Covers M31 and the port-plan Retirement checklist. Requires 00150–00154 complete, including live qualification; code removal must not imply that host-local cleanup already happened.

### Target Users
The vault owner and unattended agents using bim. Tests use scratch vaults and isolated HOME/XDG_STATE_HOME; never the private vault.

### Success Metrics
`uv run python tools/lib/check_bim_tx_port.py` verifies every inventory row's test/doc/config evidence, replacement commands, retired package/wiring and qualified backend report. `rg -i klyreon src tests docs/source pyproject.toml` must exit 1 with no matches (exit 2 is failure). Host leftovers are a separately tracked closure item, never silently marked removed.

## Functional Decomposition

### Capability: Proven retirement
#### Feature: Inventory evidence gate
- **Description**: Prove port completion before deleting source or tests.
- **Inputs**: Every row of processed intake port-plan.md, source revision e78fee4c and current source diff; 00150–00154 results.
- **Outputs**: Row-by-row coverage report with port/redesign/drop and evidence.
- **Behavior**: Premise: replacement behavior and consumer cutover are complete and the source inventory remains exhaustive. Recheck at execution, including the config-local-layer-braid source changes; failed premise means skip deletion and report, never force. Every code-only port defect gets a named regression distinguishing old/new behavior; unchanged rows retain parity cases. Include export schema/--out refusal, status counters/staleness, maintain no-op/dry-run, schedule hashes, confinement, every setting, git gate/scoping/lock/rollback, lifecycle/assent/MOCs and every format row. Headless coverage check fails on missing evidence; a skipped deletion is not a completed retirement.
#### Feature: Remove package and consumers
- **Description**: Remove obsolete wiring and source after evidence passes.
- **Inputs**: Exact source/test/docs inventory and pyproject entry/package/pytest marker.
- **Outputs**: Only bim owns these capabilities; retained historical references stay as history.
- **Behavior**: Remove src/tools/klyreon and tests/tools/klyreon only after their retained cases run from bim tests without cross-tool imports. Remove entry point, wheel package and marker, docs page and tools index links; move four background reference documents to docs/reference/bim/tiromex and retain the revised format spec there. No old skill pack, init/root config/assets installer/manifest, dead human-author helper or source clock skew survives. Keep CHANGELOG history and research/discovery archives; add a Removed entry. Tests checking absence must not themselves embed an unbroken retired tool name under src/tests.
### Capability: Host cleanup handoff
#### Feature: Prepare recoverable local cleanup
- **Description**: Record the authorized cleanup outside this repository as a separate host task.
- **Inputs**: Known ~/.config/klyreon, ~/.local/state/klyreon, dotfiles ledger entry; scheduler/install status.
- **Outputs**: Executable-order cleanup instructions and explicit pending/completed evidence fields.
- **Behavior**: Premise: config still points to a deleted temp vault, no live skill/job/vault exists, and state is stale. Instructions first recheck config, processes, launchd and Linux crontab; if false, skip/report. Use recoverable quarantine, not unrecoverable deletion; remove only the verified ledger entry through the dotfiles authority. Respect warrant and the bare-repo control-path rule. No routine PRD implementation step asks for a human response: generate/validate this handoff automatically, leave host cleanup pending for an attended authorized session if required permissions are unavailable. Do not edit ~/.buvis, host config, state or scheduler during repository retirement tests.

## Structural Decomposition

### Repository Structure
```text
src/tools/klyreon/                         # removal inventory in Module Locations
tests/tools/klyreon/                      # remove only after coverage gate
docs/source/tools/klyreon.rst              # remove
docs/reference/bim/tiromex/                # preserved references
pyproject.toml
docs/source/tools.rst
README.md
AGENTS.md
CHANGELOG.md
tools/lib/check_bim_tx_port.py
tests/tools/bim/tx/test_port_completion.py
docs/dev/project-management/reviews/00155-bim-tx-port-coverage.md
docs/dev/procedures/retire-klyreon-host.md
```

### Module: Port evidence
- **Maps to capability**: Proven retirement
- **Location**: `tools/lib/check_bim_tx_port.py`, `tests/tools/bim/tx/test_port_completion.py`, `docs/dev/project-management/reviews/00155-bim-tx-port-coverage.md`
- **Responsibility**: Headless inventory coverage validator, completion tests and durable evidence report.
- **Exports**: Headless inventory coverage validator, completion tests and durable evidence report.
New symbols: `tools/lib/check_bim_tx_port.py`, `tests/tools/bim/tx/test_port_completion.py`, `docs/dev/project-management/reviews/00155-bim-tx-port-coverage.md`
### Module: Package removal
- **Maps to capability**: Proven retirement
- **Location**: `src/tools/klyreon/__init__.py`, `src/tools/klyreon/__main__.py`, `src/tools/klyreon/assets/__init__.py`, `src/tools/klyreon/assets/installer.py`, `src/tools/klyreon/assets/manifest.py`, `src/tools/klyreon/assets/payload/claude/skills/klyreon/SKILL.md`, `src/tools/klyreon/assets/registry.py`, `src/tools/klyreon/backends/__init__.py`, `src/tools/klyreon/backends/base.py`, `src/tools/klyreon/backends/claude.py`, `src/tools/klyreon/backends/stub.py`, `src/tools/klyreon/cli.py`, `src/tools/klyreon/commands/__init__.py`, `src/tools/klyreon/commands/assets.py`, `src/tools/klyreon/commands/export_claims.py`, `src/tools/klyreon/commands/ingest.py`, `src/tools/klyreon/commands/init.py`, `src/tools/klyreon/commands/maintain.py`, `src/tools/klyreon/commands/new.py`, `src/tools/klyreon/commands/schedule.py`, `src/tools/klyreon/commands/status.py`, `src/tools/klyreon/commands/validate.py`, `src/tools/klyreon/ingest/__init__.py`, `src/tools/klyreon/ingest/conflicts.py`, `src/tools/klyreon/ingest/moc.py`, `src/tools/klyreon/ingest/pipeline.py`, `src/tools/klyreon/ingest/render.py`, `src/tools/klyreon/maintain/__init__.py`, `src/tools/klyreon/maintain/graph.py`, `src/tools/klyreon/maintain/moc_sync.py`, `src/tools/klyreon/maintain/prune.py`, `src/tools/klyreon/maintain/rules.py`, `src/tools/klyreon/maintain/sweep.py`, `src/tools/klyreon/manifest.toml`, `src/tools/klyreon/prompts/__init__.py`, `src/tools/klyreon/prompts/ingest.md`, `src/tools/klyreon/run/__init__.py`, `src/tools/klyreon/run/lock.py`, `src/tools/klyreon/run/staging.py`, `src/tools/klyreon/run/trail.py`, `src/tools/klyreon/schedule/__init__.py`, `src/tools/klyreon/schedule/cron.py`, `src/tools/klyreon/schedule/installer.py`, `src/tools/klyreon/schedule/launchd.py`, `src/tools/klyreon/settings.py`, `src/tools/klyreon/spec/__init__.py`, `src/tools/klyreon/spec/enums.py`, `src/tools/klyreon/spec/model.py`, `src/tools/klyreon/spec/parser.py`, `src/tools/klyreon/spec/validator.py`, `src/tools/klyreon/spec/writer.py`, `src/tools/klyreon/vault/__init__.py`, `src/tools/klyreon/vault/config.py`, `src/tools/klyreon/vault/git.py`, `src/tools/klyreon/vault/ids.py`, `src/tools/klyreon/vault/paths.py`, `src/tools/klyreon/vault/state.py`
- **Responsibility**: Remove the obsolete package after the evidence gate.
- **Exports**: Remove the obsolete package after the evidence gate.
### Module: Test retirement
- **Maps to capability**: Proven retirement
- **Location**: `tests/tools/klyreon/assets/__init__.py`, `tests/tools/klyreon/assets/test_commands_assets_cli.py`, `tests/tools/klyreon/assets/test_installer.py`, `tests/tools/klyreon/assets/test_manifest.py`, `tests/tools/klyreon/assets/test_registry.py`, `tests/tools/klyreon/assets/test_wheel_resolution.py`, `tests/tools/klyreon/conftest.py`, `tests/tools/klyreon/fixtures/ingest/architecture-moc.md`, `tests/tools/klyreon/fixtures/ingest/conflict-sources/conflict-aporia-doubt.md`, `tests/tools/klyreon/fixtures/ingest/conflict-sources/conflict-aporia-zettel.md`, `tests/tools/klyreon/fixtures/ingest/conflict-sources/conflict-refine.md`, `tests/tools/klyreon/fixtures/ingest/conflict-sources/conflict-rejected-target.md`, `tests/tools/klyreon/fixtures/ingest/conflict-sources/conflict-supersede.md`, `tests/tools/klyreon/fixtures/ingest/conflict-vault/sources/archive/2026-03/article-certainty.md`, `tests/tools/klyreon/fixtures/ingest/conflict-vault/sources/archive/2026-03/article-probabilism.md`, `tests/tools/klyreon/fixtures/ingest/conflict-vault/wiki/mocs/epistemics.md`, `tests/tools/klyreon/fixtures/ingest/conflict-vault/wiki/notes/20260301090000.md`, `tests/tools/klyreon/fixtures/ingest/conflict-vault/wiki/notes/20260301093000.md`, `tests/tools/klyreon/fixtures/ingest/payloads.py`, `tests/tools/klyreon/fixtures/ingest/sources/2026-05/article-cache-invalidation.md`, `tests/tools/klyreon/fixtures/ingest/sources/2026-05/book-thinking-fast-slow-ch1.md`, `tests/tools/klyreon/fixtures/ingest/sources/2026-05/quote-brooks-no-silver-bullet.md`, `tests/tools/klyreon/fixtures/ingest/sources/2026-05/transcript-arch-review-2026-05-01.md`, `tests/tools/klyreon/fixtures/valid/sources/archive/2026-04/article-resilience-patterns.md`, `tests/tools/klyreon/fixtures/valid/wiki/mocs/architecture.md`, `tests/tools/klyreon/fixtures/valid/wiki/notes/20260408180230.md`, `tests/tools/klyreon/fixtures/valid/wiki/notes/20260411145300.md`, `tests/tools/klyreon/fixtures/valid/wiki/trails/20260411150000.md`, `tests/tools/klyreon/ingest/__init__.py`, `tests/tools/klyreon/ingest/conftest.py`, `tests/tools/klyreon/ingest/test_backends_base.py`, `tests/tools/klyreon/ingest/test_backends_claude.py`, `tests/tools/klyreon/ingest/test_conflicts.py`, `tests/tools/klyreon/ingest/test_contradiction_scenarios.py`, `tests/tools/klyreon/ingest/test_fixtures_validate.py`, `tests/tools/klyreon/ingest/test_moc.py`, `tests/tools/klyreon/ingest/test_pipeline.py`, `tests/tools/klyreon/ingest/test_prompts.py`, `tests/tools/klyreon/ingest/test_render.py`, `tests/tools/klyreon/ingest/test_run_lock.py`, `tests/tools/klyreon/ingest/test_staging.py`, `tests/tools/klyreon/maintain/__init__.py`, `tests/tools/klyreon/maintain/conftest.py`, `tests/tools/klyreon/maintain/test_cli.py`, `tests/tools/klyreon/maintain/test_criterion4.py`, `tests/tools/klyreon/maintain/test_graph.py`, `tests/tools/klyreon/maintain/test_moc_sync.py`, `tests/tools/klyreon/maintain/test_prune.py`, `tests/tools/klyreon/maintain/test_rules.py`, `tests/tools/klyreon/maintain/test_sweep.py`, `tests/tools/klyreon/schedule/__init__.py`, `tests/tools/klyreon/schedule/test_installer.py`, `tests/tools/klyreon/schedule/test_renderers.py`, `tests/tools/klyreon/test_commands_cli.py`, `tests/tools/klyreon/test_commands_export_claims.py`, `tests/tools/klyreon/test_no_bare_writes.py`, `tests/tools/klyreon/test_phase0.py`, `tests/tools/klyreon/test_scenarios.py`, `tests/tools/klyreon/test_spec_parser_writer.py`, `tests/tools/klyreon/test_spec_validator_file.py`, `tests/tools/klyreon/test_spec_validator_vault.py`, `tests/tools/klyreon/test_vault_config_paths.py`, `tests/tools/klyreon/test_vault_git.py`, `tests/tools/klyreon/test_vault_ids.py`, `tests/tools/klyreon/test_vault_state.py`
- **Responsibility**: Remove superseded tests only after every retained case has bim coverage.
- **Exports**: Remove superseded tests only after every retained case has bim coverage.
### Module: Documentation and wiring
- **Maps to capability**: Proven retirement
- **Location**: `docs/reference/klyreon/ancient-philosophy-applied-to-zettelkasten.md`, `docs/reference/klyreon/anti-example-prior-build-output.md`, `docs/reference/klyreon/lessons-from-prior-iterations.md`, `docs/reference/klyreon/original-karpathy-idea-proposal.md`, `docs/reference/klyreon/zettel-format-specification.md`, `docs/reference/bim/tiromex/ancient-philosophy-applied-to-zettelkasten.md`, `docs/reference/bim/tiromex/anti-example-prior-build-output.md`, `docs/reference/bim/tiromex/lessons-from-prior-iterations.md`, `docs/reference/bim/tiromex/original-karpathy-idea-proposal.md`, `docs/source/tools/klyreon.rst`, `docs/source/tools.rst`, `docs/source/tools/bim.rst`, `pyproject.toml`, `README.md`, `AGENTS.md`, `CHANGELOG.md`
- **Responsibility**: Consolidated bim documentation, preserved background references and package wiring.
- **Exports**: Consolidated bim documentation, preserved background references and package wiring.
New symbols: `docs/reference/bim/tiromex/ancient-philosophy-applied-to-zettelkasten.md`, `docs/reference/bim/tiromex/anti-example-prior-build-output.md`, `docs/reference/bim/tiromex/lessons-from-prior-iterations.md`, `docs/reference/bim/tiromex/original-karpathy-idea-proposal.md`
### Module: Host closure
- **Maps to capability**: Host cleanup handoff
- **Location**: `docs/dev/procedures/retire-klyreon-host.md`
- **Responsibility**: Ordered, recoverable cleanup handoff with explicit external completion status.
- **Exports**: Ordered, recoverable cleanup handoff with explicit external completion status.
New symbols: `docs/dev/procedures/retire-klyreon-host.md`

## Dependency Graph

### Foundation Layer (Phase 0)
- **Port evidence**: Depends on 00150–00154; all inventory rows and live qualification must already have evidence.

### Core Layer (Phase 1)
- **Package removal**, **Test retirement**: Each depends on [Port evidence].

### Integration Layer (Phase 2)
- **Documentation and wiring**: Depends on [Package removal, Test retirement]. **Host closure**: Depends on [Port evidence]; external execution is tracked independently.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Verify the premise and coverage.

**Tasks**:
- [ ] Build the coverage report and fail-closed validator (depends on: 00150–00154). Acceptance: `uv run python tools/lib/check_bim_tx_port.py --pre-retirement` verifies every inventory row and existing replacement tests/live qualification; `uv run pytest tests/tools/bim/tx/test_port_completion.py -k premise` proves missing evidence or new source behavior prevents deletion.

**Exit Criteria**: Every approved row has specific passing test/doc/config evidence; source drift is reconciled without new unapproved drops.

### Phase 1: Core
**Goal**: Remove superseded code and consolidate references.

**Tasks**:
- [ ] Recheck coverage and source revision immediately before removing enumerated package/tests and pyproject wiring (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/tx/test_port_completion.py -k package` and `uv run python tools/lib/check_tool_wiring.py` prove retired entry/package/marker absent and replacement commands remain; failed premise skips/reports instead of deleting.
- [ ] Move the four background references, retain revised format spec, remove old docs page/index entry, update README/root guidance/bim docs/changelog (depends on: package removal). Acceptance: `uv run pytest tests/tools/bim/tx/test_port_completion.py -k docs` verifies retained reference contents, revised format destination and no dangling active-doc links.

**Exit Criteria**: Active src/tests/docs/source/pyproject contain no retired-name reference; archival research and changelog history remain.

### Phase 2: Integration
**Goal**: Close repository checks and prepare host follow-up.

**Tasks**:
- [ ] Write the host cleanup handoff and pending closure record (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/tx/test_port_completion.py -k host_handoff` checks preconditions precede actions, both scheduler platforms are checked, recoverable quarantine and warrant handling are explicit; no host writes occur.
- [ ] Run final inventory/consumer check (depends on: Phase 1 and host handoff). Acceptance: `uv run python tools/lib/check_bim_tx_port.py` rejects incomplete coverage, leftover imports/wiring or missing host status; retired-name scan returns exactly 1.

**Exit Criteria**: `uv run pytest`, `uv run mypy src/lib/ src/tools/`, `uv run sphinx-build -b html docs/source docs/build/html` and `uv build` pass once at closeout. CI must also pass for the exact removal commit after the authorized normal push; pending or failed CI leaves retirement incomplete. Report repository retirement separately from pending host cleanup.

## Test Strategy

### Critical Scenarios
- **Happy path**: every port row maps to replacement evidence and all removed commands have intended replacements/drops.
- **Edge case**: new source behavior or live legacy data appears after authoring; deletion is skipped and retirement remains incomplete.
- **Error case**: missing replacement test, absent live qualification, dangling docs link or old wheel entry makes the validator fail.
- **Integration**: test fixtures simulate host leftovers and permission denial; never manipulate the actual host as test setup.

## Risks

- **Silent test loss**: preserve behavior-level assertions and link every retained source test category before removal.
- **External permissions**: host cleanup may require warrant/user execution; the prepared handoff is the repository deliverable, and M31's host portion remains visibly pending until executed.
- **Historical text**: limit the no-name scan to active code/tests/docs/source/pyproject; reference background and project history may retain provenance.

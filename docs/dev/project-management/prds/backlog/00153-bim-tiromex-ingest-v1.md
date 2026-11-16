---
design: run
default_model: opus
model_tier_rationale: invented provenance algorithm plus concurrency, rollback and backend cancellation
eligibility: test -f docs/dev/project-management/prds/done/00152-bim-tiromex-mirrors-v1.md && curl -sf -m 5 http://127.0.0.1:8080/v1/models
---

# bim tx mirror ingestion and conflict handling

Source: [Discovery 00149](docs/dev/project-management/intake/processed/00149-merge-klyreon-into-bim/discovery.md); adjacent port-plan.md supplies the approved inventory. Discovery overrides older examples. Part 4 of 6; explicit discovery numbering is retained.

Grounding: `ingest_source` at `src/tools/klyreon/ingest/pipeline.py:108-120` and `Staging` at `src/tools/klyreon/run/staging.py:67-77` are port references, not dependencies of the new implementation.

## Overview

### Problem Statement
Port source-to-claim ingestion into tiromex with immutable mirrors, incremental provenance and safe shared-vault commits. Covers M10, M22–M24a and ingest parts of M28/M29. Requires 00150–00152 complete.

### Target Users
The vault owner and unattended agents using bim. Tests use scratch vaults and isolated HOME/XDG_STATE_HOME; never the private vault.

### Success Metrics
`uv run pytest tests/tools/bim/tx/test_sources.py tests/tools/bim/tx/test_ingest.py tests/tools/bim/tx/test_conflicts.py tests/tools/bim/tx/test_run_safety.py` passes. Live qualification runs Claude and the host's llama.cpp server (OpenAI-compatible endpoint http://127.0.0.1:8080, model unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL; Ollama is not installed on this host, checked 2026-11-16) through three fresh complete fixture runs each; write actual versions/model IDs/results to the qualification report. Missing providers fail qualification explicitly, never count skipped tests as success.

## Functional Decomposition

### Capability: Incremental mirror sources
#### Feature: Pending sources and provenance
- **Description**: Select stable mirror files by root/path and content hash.
- **Inputs**: Named roots, per-source hash records, mirror_settle_minutes default 10, max_sources_per_run default 5.
- **Outputs**: Pending/deferred inputs and successful-source records under XDG_STATE_HOME/bim/tx.
- **Behavior**: Sort by root name then full path. Skip files newer than the settle window; changed hashes are pending again. Accept Markdown with or without frontmatter; never move/copy/modify originals. Status uses the identical pending predicate. Explicit PATH reads a configured mirror file in place; for an unregistered file require registering its parent first (guess). Missing paths return CommandResult failure. A pending file matching a known hash whose old path is gone moves the record and citations without an LLM; do not treat still-present identical copies as moves. Source-dependent operations skip absent hosts.
#### Feature: Changed-source updates
- **Description**: Avoid duplicate claims and false evidence when a source changes.
- **Inputs**: Existing notes linked to that source and its changed text.
- **Outputs**: Edits limited to that source's notes, plus notes for new material.
- **Behavior**: Tell the backend which notes came from the source. Permit only existing-note edits within that source's provenance; same-source matches are neither conflicts nor corroboration. Persist a successful hash only after its scoped note commit; retry interrupted work safely. Rebuild the claim index after each committed source so later inputs can see it. Resolve ambiguous identical-hash move candidates conservatively without guessing a source owner.
### Capability: Safe ingest transactions
#### Feature: Schema and conflict port
- **Description**: Preserve aporia/refine/supersede behavior using bim notes.
- **Inputs**: Shared backend registry, shipped prompt, tx claim set and optional tiromex voice.
- **Outputs**: Validated IngestPayload-derived drafts, conflicts and corroborations.
- **Behavior**: Port source payload fields, closed shapes and extra=forbid; add only the provenance-bound edit support needed above. Backend receives source text and tiromex context only, never private notes or vault paths/tool access. Confine every MOC/doubt/edit target, including symlinks. Bad targets fail only that source. Preserve rejected-target behavior. Read voice from tiromex with built-in fallback; do not send starter placeholder text. No source-index clock offset; bump id/date on collisions. MOCs preserve prose and skip malformed existing member blocks.
#### Feature: Scoped apply, rollback and journal
- **Description**: Keep each source's write set isolated from other agents.
- **Inputs**: Per-vault lock shared with maintain; clean target snapshots; tx git identity.
- **Outputs**: Exact-path commits, byte-for-byte rollback and one run note when work/failure occurred.
- **Behavior**: Refuse outside a git work tree. Use atomic writes, reusable lock and staging in XDG_STATE_HOME/bim/tx; release/clean on BaseException. Never stage, edit or restore another agent's dirty/untracked existing file; skip its proposed edit and journal it while a new note can land. Recheck cleanliness/ownership before apply and commit. Preserve unrelated index changes. One scoped commit per source uses configured identity and unsigned environment overrides. One aggregate tx-run journal in tiromex/runs records changed/committed/failed work; include it in run commits rather than creating one journal per source. A caught source failure records its failure; interruption during an outstanding backend call leaves no note/commit/hash and the next run retries. No-op creates no journal. Dry-run writes nothing anywhere, including temp dirs, locks, staging and state.

## Structural Decomposition

### Repository Structure
```text
src/tools/bim/commands/tx/shared/      # source tracking and transactions
src/tools/bim/commands/tx/ingest.py
src/tools/bim/commands/tx/prompts/ingest.md
tests/tools/bim/tx/                    # fixtures and regression checks
tools/lib/qualify_bim_tx.py
docs/dev/project-management/reviews/00153-bim-tx-backends.md
CHANGELOG.md
docs/source/tools/bim.rst
src/tools/bim/SKILL.md
src/tools/bim/commands/tx/cli.py
src/tools/bim/commands/tx/prompts/__init__.py
src/tools/bim/commands/tx/status.py
src/tools/bim/dependencies.py
```

### Module: Source tracking
- **Maps to capability**: Incremental mirror sources
- **Location**: `src/tools/bim/commands/tx/shared/sources.py`, `src/tools/bim/commands/tx/shared/state.py`, `tests/tools/bim/tx/test_sources.py`
- **Responsibility**: Stable pending selection and source provenance.
- **Exports**: Stable pending selection and source provenance.
New symbols: `src/tools/bim/commands/tx/shared/sources.py`, `src/tools/bim/commands/tx/shared/state.py`, `tests/tools/bim/tx/test_sources.py`
### Module: Run persistence
- **Maps to capability**: Safe ingest transactions
- **Location**: `src/tools/bim/commands/tx/shared/git.py`, `src/tools/bim/commands/tx/shared/lock.py`, `src/tools/bim/commands/tx/shared/staging.py`, `src/tools/bim/commands/tx/shared/journal.py`, `src/tools/bim/commands/tx/shared/state.py`, `tests/tools/bim/tx/test_run_safety.py`
- **Responsibility**: Scoped git apply, lock, rollback and aggregate run journal.
- **Exports**: Scoped git apply, lock, rollback and aggregate run journal.
New symbols: `src/tools/bim/commands/tx/shared/git.py`, `src/tools/bim/commands/tx/shared/lock.py`, `src/tools/bim/commands/tx/shared/staging.py`, `src/tools/bim/commands/tx/shared/journal.py`, `src/tools/bim/commands/tx/shared/state.py`, `tests/tools/bim/tx/test_run_safety.py`
### Module: Ingest pipeline
- **Maps to capability**: Safe ingest transactions
- **Location**: `src/tools/bim/commands/tx/ingest.py`, `src/tools/bim/commands/tx/shared/sources.py`, `src/tools/bim/commands/tx/shared/payload.py`, `src/tools/bim/commands/tx/shared/pipeline.py`, `src/tools/bim/commands/tx/shared/render.py`, `src/tools/bim/commands/tx/shared/conflicts.py`, `src/tools/bim/commands/tx/shared/moc.py`, `src/tools/bim/commands/tx/prompts/__init__.py`, `src/tools/bim/commands/tx/prompts/ingest.md`, `tests/tools/bim/tx/test_ingest.py`, `tests/tools/bim/tx/test_conflicts.py`, `tests/tools/bim/tx/test_run_safety.py`, `tests/tools/bim/tx/test_live_ingest.py`, `tests/tools/bim/tx/fixtures/ingest.py`, `tools/lib/qualify_bim_tx.py`, `docs/dev/project-management/reviews/00153-bim-tx-backends.md`, `src/tools/bim/commands/tx/cli.py`, `src/tools/bim/commands/tx/status.py`, `src/tools/bim/commands/tx/shared/settings.py`, `src/tools/bim/dependencies.py`, `src/tools/bim/SKILL.md`, `docs/source/tools/bim.rst`, `CHANGELOG.md`
- **Responsibility**: CommandResult ingestion, strict semantic payload, shipped prompt and backend qualification.
- **Exports**: CommandResult ingestion, strict semantic payload, shipped prompt and backend qualification.
New symbols: `src/tools/bim/commands/tx/ingest.py`, `src/tools/bim/commands/tx/shared/sources.py`, `src/tools/bim/commands/tx/shared/payload.py`, `src/tools/bim/commands/tx/shared/pipeline.py`, `src/tools/bim/commands/tx/shared/render.py`, `src/tools/bim/commands/tx/shared/conflicts.py`, `src/tools/bim/commands/tx/shared/moc.py`, `src/tools/bim/commands/tx/prompts/__init__.py`, `src/tools/bim/commands/tx/prompts/ingest.md`, `tests/tools/bim/tx/test_ingest.py`, `tests/tools/bim/tx/test_conflicts.py`, `tests/tools/bim/tx/test_run_safety.py`, `tests/tools/bim/tx/test_live_ingest.py`, `tests/tools/bim/tx/fixtures/ingest.py`, `tools/lib/qualify_bim_tx.py`, `docs/dev/project-management/reviews/00153-bim-tx-backends.md`

## Dependency Graph

### Foundation Layer (Phase 0)
- **Source tracking**: Depends on 00150 format, 00152 mirrors; no new internal dependency.

### Core Layer (Phase 1)
- **Run persistence**: Depends on [Source tracking] for commit/hash ordering; reuses 00150 scoped paths.

### Integration Layer (Phase 2)
- **Ingest pipeline**: Depends on [Source tracking, Run persistence, 00151 backend registry, 00150 format].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Track pending and moved sources.

**Tasks**:
- [ ] Implement shared selection, settle window, state and hash-move recognition (depends on: 00150–00152). Acceptance: `uv run pytest tests/tools/bim/tx/test_sources.py` covers sorted cap, settling, changed hash, absent roots, explicit PATH, moved/deleted old paths, identical copies and status agreement.

**Exit Criteria**: Mirror fixtures are byte-identical; state is isolated and read-only commands create nothing.

### Phase 1: Core
**Goal**: Apply source work safely.

**Tasks**:
- [ ] Implement git/lock/staging/journal and dirty-target safeguards (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/tx/test_run_safety.py` proves interrupted backend retry, BaseException release, commit failure rollback, unchanged unrelated index/dirty bytes, git refusal, identity overrides and zero-write dry-run.
- [ ] Port payload/prompt/render/conflicts/MOCs and provenance-limited edits (depends on: run persistence). Acceptance: `uv run pytest tests/tools/bim/tx/test_conflicts.py tests/tools/bim/tx/test_ingest.py` covers all three shapes, rejected/bad targets, malformed MOCs, same-source suppression, source-only edits and next-source claim visibility.

**Exit Criteria**: Every source failure is isolated; private-note sentinels never occur in recording-backend prompts.

### Phase 2: Integration
**Goal**: Qualify and expose ingestion.

**Tasks**:
- [ ] Wire CLI flags and shared composition; update skill/docs/changelog (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/bim/tx/test_ingest.py -k cli` checks backend/max-sources/timeout/dry-run and missing PATH errors.
- [ ] Build and run live qualification with the converted source/conflict fixtures (depends on: CLI integration). Acceptance: `uv run python tools/lib/qualify_bim_tx.py` fails unless Claude and the llama.cpp model served at http://127.0.0.1:8080 each pass three consecutive fresh-fixture runs, validating notes and exactly one expected conflict shape; record actual CLI/model versions, the model id that endpoint's /v1/models reports, configuration and outcomes. Other adapters run deterministic smoke tests. If local payload size fails, split drafting/conflict calls before retries and repeat the full qualification.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass once; live qualification report contains passing evidence, not a manual sign-off.

## Test Strategy

### Critical Scenarios
- **Happy path**: original source → valid concept notes → unchanged rerun no backend/commit/journal; changed source updates only its own notes.
- **Edge case**: rename source → citations/state follow with no backend; two files with the same hash but both present remain separate sources.
- **Error case**: malformed target fails one source; backend killed mid-call leaves no persisted output; dirty target is byte-identical.
- **Integration**: track all filesystem effects, git HEAD/index and sentinels; fixture builder ports every existing conflict case without depending on klyreon.
- **Live suite**: use the host's llama.cpp model at http://127.0.0.1:8080 (the eligibility check requires that server to answer before this PRD is picked); no private files, no substitution on provider unavailability.

## Risks

- **Provenance algorithm**: redesign must enforce source ownership before applying backend edits; trusting a response path is insufficient.
- **Journal versus interruption**: caught failures are journaled; interruption before any apply remains side-effect free as required by discovery.
- **Concurrent agents**: a tx lock serializes tx only, so rechecks and ownership-aware rollback remain necessary.
- **Model availability**: live qualification is a real completion gate; unavailable providers leave this PRD incomplete, without requiring a human test step.

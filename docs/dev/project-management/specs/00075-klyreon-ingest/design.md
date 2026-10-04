# klyreon B: ingest, agent backend, contradiction detection

<!-- design; migrated from PRD 00075 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/klyreon/
├── backends/
│   ├── __init__.py          # Maps to: Backend contract (registry)
│   ├── base.py              # Maps to: Backend contract (protocol, errors, response schema)
│   ├── claude.py            # Maps to: Claude adapter
│   └── stub.py              # Maps to: Backend contract (offline test double)
├── prompts/
│   └── ingest.md            # Maps to: Prompt library (package data)
├── run/
│   ├── __init__.py
│   ├── lock.py              # Maps to: Single-instance guard
│   ├── staging.py           # Maps to: Atomic staging and apply
│   └── trail.py             # Maps to: Trail file per run
└── ingest/
    ├── __init__.py
    ├── pipeline.py          # Maps to: Per-source pipeline, Inbox sweep and run bounds
    ├── render.py            # Maps to: Per-source pipeline, Split rule
    ├── conflicts.py         # Maps to: Conflict resolution, Corroboration recording
    └── moc.py               # Maps to: MOC authoring
    commands/ingest.py       # Maps to: Inbox sweep and run bounds (CommandIngest)
tests/tools/klyreon/ingest/  # + fixtures/sources (4 types), fixtures/conflicts (5 cases)
```

### Module: klyreon.backends
- **Maps to capability**: Agent backend abstraction
- **Responsibility**: Turn a prompt into a validated payload. Knows nothing about zettels or the vault.
- **Exports**:
  - `get_backend(name)` - registry lookup, `claude` and `stub` today, kiro/copilot later
  - `Backend.run(prompt, timeout) -> IngestPayload` - the whole contract
  - `BackendError(reason, detail)` - `timeout` / `exit` / `parse` / `schema`
  - `IngestPayload` - pydantic model: `zettels[]`, `conflicts[]`, `corroborations[]`

### Module: klyreon.run
- **Maps to capability**: Ingest pipeline + Run journal
- **Responsibility**: Machinery both `ingest` and (PRD D) `maintain` need: the lock, the staging area, the trail writer.
- **Exports**:
  - `vault_lock(root)` - context manager, releases in `finally`
  - `Staging(run_id, source)` - `stage(rel_path, content)`, `apply(root)`, `rollback()`
  - `write_trail(root, run, entries)` - the run journal

### Module: klyreon.ingest
- **Maps to capability**: Ingest pipeline + Contradiction and corroboration
- **Responsibility**: Orchestrate one source end to end, and turn a payload into files. No console, no Click.
- **Exports**:
  - `ingest_source(root, source_path, claim_set, backend) -> SourceOutcome`
  - `render_zettels(payload, source_archive_path, root)` - payload to validated documents
  - `apply_conflicts(payload, root)` / `apply_corroborations(payload, root)`
  - `ensure_moc(root, moc_path, members)` - create or append inside the marker block

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00074 must be in `done/` (spec engine, `resolve_root`, `allocate_id`, `commit`, `require_git_for_autonomy`, `export-claims`).

- **klyreon.backends.base + stub**: no internal dependencies beyond the payload schema.
- **klyreon.run.lock**: no internal dependencies.
- **klyreon.prompts**: no internal dependencies.

### Core Layer (Phase 1)
- **klyreon.backends.claude**: depends on [backends.base]
- **klyreon.run.staging**: depends on [00074 spec.writer, 00074 vault.git]
- **klyreon.ingest.render**: depends on [00074 spec.model, 00074 vault.ids, backends.base]
- **klyreon.ingest.conflicts**: depends on [00074 spec.model, ingest.render]
- **klyreon.ingest.moc**: depends on [00074 spec.writer]

### Integration Layer (Phase 2)
- **klyreon.run.trail**: depends on [ingest.pipeline outcomes, 00074 spec.writer]
- **klyreon.ingest.pipeline**: depends on [backends, staging, render, conflicts, moc]
- **klyreon.commands.ingest + cli**: depends on [pipeline, run.lock, 00074 vault.git]

## Test Strategy

### Critical Scenarios
- **Happy path**: four fixture sources, one per spec source type, stub backend → Expected: spec-valid zettels with claims, doubts, `mocs`, and archive-path `sources`; one trail; `validate` clean; four commits plus the trail commit.
- **Contradiction**: five fixture sources against a vault holding an accepted claim → Expected: each resolves into exactly one of aporia, refine, supersede, with the exact link and doubt set; three consecutive runs of the set produce the same shapes.
- **Edge case**: a conflict whose target is `assent: rejected` → Expected: no aporia, no edit, one trail line recording the corroborated rejection.
- **Edge case**: two zettels from one source anchoring to the same missing MOC → Expected: the MOC is created once and lists both.
- **Error case**: backend killed mid-source → Expected: no zettel, no archive move, no staging left, source still in the inbox, trail records the failure, exit 1; the next run ingests it cleanly.
- **Error case**: the payload's body exceeds the ceiling → Expected: source fails with the split rule named; nothing staged.

### Quality rubric (discovery criterion 6, fixed here)
Run as a test over ingest output. R1 every file has `id`, `title`, `created`, `type`. R2 filename is 14 digits, `id` equals the stem, `created` agrees. R3 body within `max_zettel_body_lines` and at most four H2 sections. R4 every assertion-bearing zettel carries one to three claims, each one sentence of at most 40 words with no "but"/"however". R5 no intra-vault Markdown link in the body and no "Further Reading" or "Back to" section: cross-references live in frontmatter. R6 no bare numeric footnote marker, and every `sources` path resolves. R7 none of the banned register words (leverage, seamless, robust, enhance, sophisticated, cutting-edge, holistic, synergy, streamline, delve). R8 every concept zettel names at least one MOC.

## Risks

- **Operator CLI interface drift**: the claude adapter is the one place flags leak in. Flags verified 2026-08-07 and pinned in the PRD, re-recorded in docs with the known-good CLI version at implementation time, and isolated behind the `Backend` protocol so kiro and copilot land without touching the pipeline. `--json-schema` moves shape enforcement into the CLI, so drift shows up as a clean `BackendError`, not a silent misparse.
- **Backend judgment quality**: contradiction detection is only as good as the operator LLM. The five conflict fixtures are the eval, and criterion 2 gates release. The rubric test catches quality regression that validation cannot see.
- **A pathological source fails forever**: it consumes one slot per run and is named in every trail. The manual fix is to split or delete it. No failure counter, because that would be resume state on disk (discovery Q16).
- **Claim set outgrows the context window**: known ceiling at roughly 5-10k notes. `export-claims` already takes an optional scope so sharding lands without changing callers.
- **Hard kill during apply**: bounded to the milliseconds between the first file write and the commit. `validate` reports the partial state; documented, and marked in code with the upgrade path.

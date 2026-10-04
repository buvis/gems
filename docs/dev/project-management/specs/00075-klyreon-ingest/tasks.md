# klyreon B: ingest, agent backend, contradiction detection

<!-- tasks; migrated from PRD 00075 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: The backend seam and the fixtures, both testable offline.

**Tasks**:
- [ ] `backends/base.py`: `Backend` protocol, `BackendError`, and the `IngestPayload` pydantic schema (`zettels[]` with title/type/concept-type/claims/doubts/tags/mocs/body; `conflicts[]` with new-zettel index, new claim id, target `{to, claim}`, shape, rationale; `corroborations[]` with new-zettel index, target, rationale) (no deps) - Acceptance: schema round-trip test; a payload naming a shape outside {aporia, refine, supersede} is rejected.
- [ ] `backends/stub.py` plus the fixture corpus: four source documents (article, book, quote, transcript), one accepted-claim vault, five conflict cases, and their canned payloads (no deps) - Acceptance: fixtures load and validate under 00074's `validate_vault`.
- [ ] `run/lock.py`: the flock guard (no deps) - Acceptance: a second in-process acquisition returns "busy"; the lock is released after a raised `KeyboardInterrupt`; a killed process leaves no stale lock.
- [ ] `prompts/ingest.md` plus the loader, including the default voice used when `<root>/voice.md` is absent (no deps) - Acceptance: assembly test proves the source body, voice, split rule, claim set, and response schema all reach the prompt.

**Exit Criteria**: A stub backend answers a prompt and the payload validates. Nothing touches the network.

### Phase 1: Core
**Goal**: A payload becomes correct files.

**Tasks**:
- [ ] `ingest/render.py`: payload to documents, with ID allocation, archive-first `sources`, defaults, H1, and the split rule (depends on: Phase 0) - Acceptance: rendered zettels pass `validate_file`; a four-claim zettel and a 61-line body each fail with their own rule; `sources` names the archive path, never the inbox path.
- [ ] `ingest/conflicts.py`: the three shapes plus corroboration, including the rejected-target drop and the `processed` reset rules (depends on: Phase 0) - Acceptance: one test per shape asserting the exact link and doubt set on both sides; supersede leaves the loser's `processed` untouched while aporia resets the edited zettel's; a conflict targeting a `rejected` zettel produces no edit and one trail line.
- [ ] `ingest/moc.py`: create and append inside the marker block (depends on: Phase 0) - Acceptance: a MOC with human prose above and below the block keeps both after two appends; a missing MOC is created and validates as `kind: moc`.
- [ ] `run/staging.py`: stage, apply, rollback, scoped commit (depends on: Phase 0) - Acceptance: an exception mid-apply leaves the vault byte-identical to its pre-apply state, the source still in the inbox, and the staging directory gone.
- [ ] `backends/claude.py`: headless invocation with the pinned flag set, timeout kill, envelope parse plus `IngestPayload` validation, missing-binary message; record the invocation and the known-good CLI version in the docs page (depends on: Phase 0) - Acceptance: subprocess-mocked tests for success, non-zero exit, timeout, unparseable stdout, schema-mismatched payload, and absent binary, each mapping to its own `BackendError` reason; a test asserts the argv carries `--json-schema` and `--tools ""`.

**Exit Criteria**: Every piece of the pipeline is tested in isolation against the stub.

### Phase 2: Integration
**Goal**: `klyreon ingest` end to end.

**Tasks**:
- [ ] `ingest/pipeline.py` plus `CommandIngest` and the CLI wiring: inbox sweep, cap, per-source timeout, autonomy gate, `--dry-run` (depends on: Phase 1) - Acceptance: sweeping seven fixture sources with a cap of five commits five and defers two; a stubbed timeout on source three leaves the vault untouched for that source and continues with source four; a non-git vault refuses with exit 1.
- [ ] `run/trail.py` and its commit (depends on: Phase 1) - Acceptance: a run mixing committed, failed, and deferred sources writes one trail naming all three, and the trail validates as `kind: trail`.
- [ ] Quality-rubric test over the four source types and the five conflict cases (depends on: Phase 1) - Acceptance: the eight rules below all pass, and each rule has a negative fixture proving it can fail.
- [ ] Docs page (including the pinned operator-CLI invocation), CHANGELOG Added entry, mypy strict, ruff, coverage (depends on: Phase 1) - Acceptance: all gems gates green in CI.

**Exit Criteria**: Discovery success criteria 1, 2, 5, and 6 all hold against the fixture corpus.

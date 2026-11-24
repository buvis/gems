---
default_model: opus
model_tier_rationale: several parser error boundaries and continuation semantics
---

# Isolate malformed input failures and clarify diagnostics

Source: 2026-11-16 #29, 2026-11-15 run 2 #12. Original packets in buvis/engram: docs/dev/project-management/audit-results/agoge-2026-11-16.md and docs/dev/project-management/audit-results/agoge-2026-11-15-2.md.
Decision in buvis/engram: docs/dev/project-management/audit-results/agoge-triage-2026-11-23.md. This is a bounded QA correction, not a replacement of the completed feature PRDs.

Status: HOLD in buvis/gems, blocked by the Engram port prerequisites.
Origin: buvis/engram at 226db53feac942eaeef1479355a98e7dfadfe4c3, PRD 00025; transferred on 2026-11-24 without changing its QA evidence.
Prerequisites: Port phases 1-3 must land with their exit criteria met; verify the target file map and contracts before promotion to the executable backlog.
Plan: [Engram port](../../discovery/00161-engram-port-plan.md). Transfer map: [QA ownership](../../discovery/00161-engram-qa-handoff.md).

Target rules: Python 3.11+; Click adapters and CommandResult actions; lazy imports; shared YAML settings plus the machine-local layer. Preserve the port's machine-readable output exception. Expected domain failures become CommandResult failures at command boundaries, not CLI control-flow exceptions. The main tests move to tests/tools/engram; the archived research eval is not a target gate.

Compatibility: only the defects explicitly named in this PRD may change behavior. Preserve unaffected consumer goldens and add separate negative/regression cases for corrected behavior. Do not silently regenerate all goldens. Test against temporary stores; no live database migration or rebuild is authorized by this PRD execution.

## Overview

### Problem Statement
Deeply nested inputs can escape per-file error handling and abort a harvest batch. Known config failures print tracebacks, and optional missing directories appear as unlabeled output.

### Target Users
The solo developer and local agents using Engram to index repositories and recall prior work.

### Success Metrics
Every Critical Scenario passes with synthetic data in isolated temporary roots. Historical evidence below is from the QA run, not a fresh measurement. No suite-wide test count or timing target is imposed.

## Functional Decomposition

### Capability: Isolate malformed input failures and clarify diagnostics
Apply the recorded disposition without changing unrelated behavior.

#### Feature: Contain parser failures
- **Description**: Contain parser failures.
- **Inputs**: Reviews, memory frontmatter and transcript records.
- **Outputs**: Per-file or per-record errors without loss of neighboring work.
- **Behavior**: Convert expected RecursionError at YAML/JSON parser boundaries into the existing parse-failed result. Continue harvest after a bad review and preserve its existing rows. Skip a malformed/deep transcript record while retaining valid neighboring turns. Ordinary malformed JSON already skips one record; preserve that behavior and add only the missing deep-nesting case. Do not add a blanket catch around all application exceptions.

#### Feature: Report known configuration failures
- **Description**: Report known configuration failures.
- **Inputs**: Malformed YAML, missing embedding settings fields, unreadable config and SQLite open errors.
- **Outputs**: A concise diagnostic and documented nonzero status.
- **Behavior**: Catch expected configuration and store errors at CLI boundaries and name the relevant path without raw secret values. Preserve nudge's always-zero contract and MCP's structured error result.

#### Feature: Label optional missing directories
- **Description**: Label optional missing directories.
- **Inputs**: Existing optional-directory diagnostics.
- **Outputs**: missing followed by a tab and the existing corpus:repo payload.
- **Behavior**: At the machine-output adapter, print missing<TAB>{existing value}. Preserve existing scope filtering and status exit rules; optional absence alone stays nonfatal. Document the output change.

## Structural Decomposition

### Repository Structure

Expected prerequisite file map, not a claim that the port is present. Before release from hold, compare this map with the landed port, enumerate any command-layer files needed by the tasks, and rerun grounding. Do not create substitute modules to satisfy these paths.

```text
src/tools/engram/settings.py
src/tools/engram/findings.py
src/tools/engram/harvest.py
src/tools/engram/transcripts.py
src/tools/engram/memory.py
src/tools/engram/client.py
src/tools/engram/cli.py
tests/tools/engram/test_findings.py
tests/tools/engram/test_harvest.py
tests/tools/engram/test_transcripts.py
tests/tools/engram/test_repo_memory.py
tests/tools/engram/test_cli_embedding_errors.py
tests/tools/engram/test_cli_index_status.py
docs/source/tools/engram.rst
CHANGELOG.md
```

### Module: Product correction
- **Maps to capability**: Isolate malformed input failures and clarify diagnostics
- **Responsibility**: Implement the Features in the existing modules; no new public API is required.
- **Location**: `src/tools/engram/settings.py`, `src/tools/engram/findings.py`, `src/tools/engram/harvest.py`, `src/tools/engram/transcripts.py`, `src/tools/engram/memory.py`, `src/tools/engram/client.py`, `src/tools/engram/cli.py`
- **Exports**: Ported Engram interfaces supplied by the prerequisite port.
- Source API lineage (buvis/engram): parse, harvest, chunk, parse_memory, load_config, main (source only; target uses settings and Click).

### Module: Verification and guidance
- **Maps to capability**: Isolate malformed input failures and clarify diagnostics
- **Responsibility**: Prove the regression, preserve compatibility, and explain changed behavior.
- **Location**: `tests/tools/engram/test_findings.py`, `tests/tools/engram/test_harvest.py`, `tests/tools/engram/test_transcripts.py`, `tests/tools/engram/test_repo_memory.py`, `tests/tools/engram/test_cli_embedding_errors.py`, `tests/tools/engram/test_cli_index_status.py`, `docs/source/tools/engram.rst`, `CHANGELOG.md`
- **Exports**: Existing test entry points and user documentation; no runtime exports.

## Dependency Graph

### Foundation Layer (Phase 0)
- **Verification and guidance**: No internal dependencies; establish reproductions and current premises first.
- External prerequisites: the port prerequisites stated above, plus [00165](00165-engram-validate-repository-registry-v1.md), [00163](00163-engram-verify-embedding-model-identity-v1.md). Execute these PRDs first; do not work on overlapping source modules concurrently.

### Core Layer (Phase 1)
- **Product correction**: Depends on Phase 0 evidence and the external prerequisites above.

### Integration Layer (Phase 2)
- **Verification and guidance**: Depends on Product correction for final checks and user guidance.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Establish the precise existing failure or documentation premise.

**Tasks**:
- [ ] Add regressions from Critical Scenarios in the listed test files; run each bug regression against old code and record the expected failure once. (no internal deps) - Acceptance: record command, expected failure or premise, and output for each applicable Critical Scenario. Use only planted markers and temporary data.

**Exit Criteria**: Failure evidence or current documentation premises are recorded; no secrets or live stores are involved.

### Phase 1: Core
**Goal**: Deliver the Functional Decomposition.

**Tasks**:
- [ ] Implement the specified behavior in the listed production modules, preserving the stated safety and compatibility rules. (depends on: Phase 0) - Acceptance: uv run --no-sync python -m pytest -q tests/tools/engram/test_findings.py tests/tools/engram/test_harvest.py tests/tools/engram/test_transcripts.py tests/tools/engram/test_repo_memory.py tests/tools/engram/test_cli_embedding_errors.py tests/tools/engram/test_cli_index_status.py

**Exit Criteria**: All Critical Scenarios pass; required negative checks fail clearly and preserve data as specified.

### Phase 2: Integration
**Goal**: Verify the complete correction and record its limits.

**Tasks**:
- [ ] Update the Engram tool documentation and add scoped CHANGELOG entries for the implemented behavior; run the selected tests. (depends on: Phase 1) - Acceptance: review the diff against each Feature, confirm all listed scenarios, and run git diff --check.

**Exit Criteria**: Run the full Engram gate once: uv run --no-sync pytest tests/tools/engram --cov=src/tools/engram --cov-report=term-missing --cov-fail-under=50. Run ruff check and ruff format --check on src/tools/engram and tests/tools/engram, then uv run --no-sync mypy src/lib/ src/tools/. Require the Engram cells of the repository CI matrix (Ubuntu/macOS, Python 3.11-3.15); report unavailable cells and snapshot skips explicitly. Keep existing Windows lock branch tests. No archived eval suite or live-store mutation.

## Test Strategy

### Critical Scenarios
- Harvest valid, deeply nested YAML, valid files and assert all three results, retained bad-file rows, and both valid updates.
- Transcript with a deep JSON record retains valid turns before and after; normal malformed JSON still behaves as before.
- Malformed and incomplete config produce no traceback across CLI commands; unexpected programmer errors remain visible in tests.
- Missing optional directory output is labeled and scoped, with exit 0 when it is the only issue.

### Source grounding
These are source-checkout citations; target files remain prerequisites.
- ../engram/src/engram/findings.py:1
- ../engram/src/engram/harvest.py:1
- ../engram/src/engram/transcripts.py:1
- ../engram/src/engram/memory.py:1
- ../engram/src/engram/client.py:1
- ../engram/src/engram/cli.py:1

### Original QA evidence
Verbatim evidence follows. Mocked observations retain that status; local fixture tests do not turn them into real-server measurements. Isolate fixture setup from the user's actual HOME and store.

````text
2026-11-16 #29
One example each: `reviewers: [[[[...` nested 5000 deep makes `engram harvest good.md deep.md good.md` print a `RecursionError` traceback of about 200 KB and no result lines at all. `engram.db.lock` as a dangling symlink is followed and the target is created with mode 0755. The lock as a directory ends in an uncaught `IsADirectoryError`. A transcript with one bad line is skipped whole, valid turns included. A `config.toml` with bad TOML or no `endpoint` gives a traceback from `query` (`mcp` and `nudge` report it cleanly). A diff line with form feeds is split into a fake section and aborts the pack; the path guard still held. Confidence: confirmed.
2026-11-15 run 2 #12
Every `index` and `status` run printed `discovery:scratchrepo`, rc 0. Confidence: confirmed.
````

## Risks

- Catch only known input exceptions so programming errors remain diagnosable. The report's blanket claim about any bad transcript line was broader than the current code supports.
- Do not release from hold until the prerequisite port file map and parity checks are verified. Do not touch a real store or weaken assertions to obtain a pass.

---
design: run
default_model: opus
model_tier_rationale: equivalence obligation - preserve doc behavior while sharing backend transports
eligibility: test -f docs/dev/project-management/prds/done/00150-bim-tiromex-format-v1.md
---

# bim shared schema-checked LLM backends

Source: [Discovery 00149](docs/dev/project-management/intake/processed/00149-merge-klyreon-into-bim/discovery.md); its adjacent port-plan.md supplies the approved inventory. Discovery takes precedence over older idea/Q&A/port examples. Part 2 of 6; the discovery explicitly reserves 00150–00155 instead of reusing 00149.

Grounding: `ClassifierSettings` defaults are at `src/tools/bim/commands/doc/shared/settings_models.py:130-145`; `ClaudeBackend` starts at `src/tools/klyreon/backends/claude.py:43-65`.

## Overview

### Problem Statement
tx and doc need one backend layer rather than an operator-only stack and a separate local HTTP stack. Covers M18–M21. Depends operationally on 00150 landing; the implementation has no tx-engine dependency.

### Target Users
The vault owner and unattended agents using bim; tests use scratch vaults, isolated HOME and XDG_STATE_HOME, never the private vault.

### Success Metrics
`uv run pytest tests/tools/bim/test_llm_registry.py tests/tools/bim/test_llm_backends.py tests/tools/bim/doc` preserves existing classification/extraction behavior and checks every closed error class.

## Functional Decomposition

### Capability: Shared backend execution
#### Feature: Named registry and schemas
- **Description**: Resolve named backend configurations for tx and doc.
- **Inputs**: llm map keyed by name; prompt text, timeout, caller's JSON schema.
- **Outputs**: Schema-checked JSON or timeout/exit/parse/schema failure.
- **Behavior**: Keep the layer under bim/shared, with no UI dependency and no vault path or tool access passed to providers. Separate transport from caller-owned schemas; ingest schema belongs to 00153. Reject unknown backend names/kinds and unexpected schema keys. Source BackendError categories describe operational failure, not command-layer control flow; commands return CommandResult.
#### Feature: HTTP and CLI adapters
- **Description**: Support Ollama, llama.cpp, OpenAI-compatible endpoints, Claude and configured commands.
- **Inputs**: Existing doc wire formats and Claude adapter; configured argv.
- **Outputs**: Validated responses; bounded execution and explicit errors.
- **Behavior**: Use existing HTTP client or stdlib without a new dependency. Port Claude stdin, temporary cwd, --tools empty string, schema flag, optional model and timeout cushion of 30 seconds; verify installed CLI flags headlessly. Generic command uses literal argv, stdin prompt, stdout JSON, no shell; schedule use requires unattended:true, false by default. Stub is test-only. Other named agent adapters are extensible, not mandatory new providers; never claim generic argv proves tools are disabled.
### Capability: Doc compatibility
#### Feature: Classifier and extractor cutover
- **Description**: Move both callers onto the same registry while retaining legacy config behavior.
- **Inputs**: Existing ClassifierSettings/LLMSettings, named backend/fallback references.
- **Outputs**: Unchanged doc result shapes, fallback, retries and triage behavior.
- **Behavior**: Preserve default Ollama endpoint http://localhost:11434, primary qwen3:30b-a3b, fallback qwen3:14b, triage_threshold 0.85 and max_retries 2. Existing ollama/llamacpp configs still load and resolve into the registry; named backend references select llm entries. Preserve transient versus semantic errors, extraction partial results, pinned fields and health behavior. No OCR or document storage redesign.

## Structural Decomposition

### Repository Structure
```text
src/tools/bim/shared/llm/             # registry and adapters
src/tools/bim/commands/doc/shared/    # existing consumers
src/tools/bim/settings.py
src/tools/bim/dependencies.py
tests/tools/bim/                      # exact test paths below
CHANGELOG.md
docs/source/tools/bim.rst
```

### Module: Backend registry
- **Maps to capability**: Shared backend execution
- **Location**: `src/tools/bim/shared/llm/__init__.py`, `src/tools/bim/shared/llm/base.py`, `src/tools/bim/shared/llm/settings.py`, `src/tools/bim/shared/llm/registry.py`, `src/tools/bim/shared/llm/http.py`, `src/tools/bim/shared/llm/claude.py`, `src/tools/bim/shared/llm/command.py`, `tests/tools/bim/test_llm_registry.py`, `tests/tools/bim/test_llm_backends.py`
- **Responsibility**: Named schema-aware invocation, transport adapters and closed failure categories.
- **Exports**: Named schema-aware invocation, transport adapters and closed failure categories.
New symbols: `src/tools/bim/shared/llm/__init__.py`, `src/tools/bim/shared/llm/base.py`, `src/tools/bim/shared/llm/settings.py`, `src/tools/bim/shared/llm/registry.py`, `src/tools/bim/shared/llm/http.py`, `src/tools/bim/shared/llm/claude.py`, `src/tools/bim/shared/llm/command.py`, `tests/tools/bim/test_llm_registry.py`, `tests/tools/bim/test_llm_backends.py`
### Module: Doc integration
- **Maps to capability**: Doc compatibility
- **Location**: `src/tools/bim/commands/doc/shared/llm.py`, `src/tools/bim/commands/doc/shared/classifier.py`, `src/tools/bim/commands/doc/shared/extractor.py`, `src/tools/bim/commands/doc/shared/settings_models.py`, `src/tools/bim/commands/doc/shared/health.py`, `src/tools/bim/commands/doc/shared/pipeline.py`, `src/tools/bim/commands/doc/shared/pipeline_helpers.py`, `tests/tools/bim/doc/test_classifier.py`, `tests/tools/bim/doc/test_extractor.py`, `tests/tools/bim/doc/test_llm.py`, `tests/tools/bim/doc/test_settings_models.py`, `tests/tools/bim/doc/test_dependencies.py`, `tests/tools/bim/doc/test_classifier_pinned.py`, `tests/tools/bim/doc/test_extractor_pinned.py`, `src/tools/bim/settings.py`, `src/tools/bim/dependencies.py`, `docs/source/tools/bim.rst`, `CHANGELOG.md`
- **Responsibility**: Existing Classifier and Extractor interfaces backed by the shared registry.
- **Exports**: Existing Classifier and Extractor interfaces backed by the shared registry.

## Dependency Graph

### Foundation Layer (Phase 0)
- **Backend registry**: No new PRD dependency; existing doc wire and Claude implementation are port references.

### Core Layer (Phase 1)
- **Adapters** (within Backend registry): Depends on [Backend registry].

### Integration Layer (Phase 2)
- **Doc integration**: Depends on [Backend registry, Adapters]. Land after 00150 in the port sequence.

## Implementation Phases

### Phase 0: Foundation
**Goal**: Define registry and configurable schemas.

**Tasks**:
- [ ] Implement named settings and registry with caller-provided schema validation (no deps). Acceptance: `uv run pytest tests/tools/bim/test_llm_registry.py` proves per-name selection, strict config and independent doc/tx schemas.

**Exit Criteria**: Registry tests pass without requiring installed agents or running servers.

### Phase 1: Core
**Goal**: Port transports and isolation.

**Tasks**:
- [ ] Implement the Ollama, llama.cpp and OpenAI-compatible HTTP adapters (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/test_llm_backends.py -k http` verifies request bodies, timeouts, invalid JSON/schema and that no vault path appears in a payload.
- [ ] Implement the Claude adapter (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/test_llm_backends.py -k claude` verifies envelope parsing, no-tools argv, stdin/cwd, the 30-second timeout cushion, missing executable and invalid JSON/schema.
- [ ] Implement the generic command adapter (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/bim/test_llm_backends.py -k command` verifies literal argv without a shell, stdin prompt, stdout JSON, timeouts, missing executable and unattended refusal unless unattended:true.

**Exit Criteria**: All adapter failures use the closed categories; test stub is unavailable from user configuration.

### Phase 2: Integration
**Goal**: Preserve doc behavior through shared execution.

**Tasks**:
- [ ] Rewire doc settings, health and composition onto the registry, and update docs and changelog (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/bim/doc/test_llm.py tests/tools/bim/doc/test_settings_models.py tests/tools/bim/doc/test_dependencies.py` retains behavioral assertions and legacy defaults, and proves an old config without an llm map resolves to its original endpoint and models.
- [ ] Rewire the doc classifier and extractor onto the registry (depends on: doc settings rewire). Acceptance: `uv run pytest tests/tools/bim/doc/test_classifier.py tests/tools/bim/doc/test_extractor.py tests/tools/bim/doc/test_classifier_pinned.py tests/tools/bim/doc/test_extractor_pinned.py` retains behavioral assertions, fallback, retries, triage and partial extraction results.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass once at closeout.

## Test Strategy

### Critical Scenarios
- **Happy path**: identical fake response through each backend validates against the caller's schema.
- **Edge case**: old doc configuration without llm map still runs with its original models and retry/triage behavior.
- **Error case**: timeout/nonzero exit/malformed JSON/schema mismatch map distinctly; no vault path appears in argv or payload.
- **Integration**: retain existing assertions when replacing transport mocks; adapters get deterministic smoke tests, with live Claude/local ingest qualification in 00153.

## Risks

- **Compatibility obligation**: settings and error mapping are behavior-preserving, not a rewrite of doc domain rules.
- **Generic command trust**: explicit unattended opt-in records the inability to enforce no tools.
- **Provider variation**: verify local CLI help during design; do not silently fall back to another model or provider.

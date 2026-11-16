---
default_model: opus
model_tier_rationale: New filesystem audit and failure contracts require judgment; exact behavior is specified but implementation is not transcription.
---

# sysup Herdr clone audit

Source: `docs/dev/project-management/intake/processed/00156-sysup-herdr-update/discovery.md`.
Evidence: sibling `evidence.md`. Deferred original scope: intake 00157.

## Overview

### Problem Statement
sysup updates community mods through hmod, which deliberately excludes personal
Herdr clones. Personal mod/layout provenance can silently lag behind the app
or reference a missing personal parent. Add a read-only review signal, not a
compatibility check. App/core orchestration and clone porting remain separate.

### Target Users
The solo developer maintaining personal Herdr layouts and mods through sysup.

### Success Metrics
Focused audit tests prove exact version comparison, unresolved ancestry warnings,
failure on unreadable metadata, unchanged Herdr files, and no mod execution.
CLI tests prove persistent attention, clean-audit clearing, and dry-run safety.

## Functional Decomposition

### Capability: Clone provenance audit
Inspect local provenance without loading or modifying Herdr extensions.

#### Feature: Safe inventory
- **Description**: Discover personal mod and layout clone metadata.
- **Inputs**: Nonempty HERDR_APP_HOME or ~/.config/herdr-app; installed.json;
  nonhidden immediate mod directories' mod.json and immediate layouts/*.json.
  These are runtime inventory patterns, not repository edit paths.
- **Outputs**: Existing StepResult values identifying the relative item path.
- **Behavior**: Resolve the home as the allowed root. Require installed.json to
  be a JSON object whose values are objects; its plain keys identify shipped
  mods and layout:-prefixed keys identify shipped layouts. Skip those shipped
  entries. Read personal JSON objects; absent mod.json means no declared clone,
  while an unreadable existing manifest or invalid JSON/object fails that item.
  A missing/unreadable installed.json, mods directory, or layouts directory fails
  the audit. Ignore dotfiles and nested layout state. Resolve every candidate
  and require it under the resolved home before reading; an escaping or broken
  symlink fails that item, including symlinked inventory roots. Continue through
  independent item errors. Never follow a path built from cloned_from.name.

#### Feature: Version and ancestry signals
- **Description**: Report provenance requiring review without claiming compatibility.
- **Inputs**: The resolved herdr-app executable's --version output and each
  personal object's optional cloned_from field.
- **Outputs**: Warned review signals, failed invalid-input results, or an ok
  summary that explicitly says compatibility was not checked.
- **Behavior**: Run only `[herdr-app, --version]`, without a shell, with a
  ten-second timeout and captured output. Require exit zero and stripped output
  matching `herdr-app <one-non-whitespace-version-token>` exactly. Missing binary,
  launch error, timeout, or invalid version output fails without comparing clones.
  Omitted cloned_from means no clone. A present value must be an object with
  nonempty string name and version; name must be a basename other than . or ..,
  with neither slash nor backslash. Invalid metadata fails that item.
  Compare version strings exactly, without ordering or normalization. A mismatch
  yields success=True/status=warned and identifies clone, source, recorded version,
  and CLI binary version. Source membership uses the same asset kind in
  installed.json; a source absent from that set is unresolved/personal ancestry
  and warns even if versions match. A source in the set must also exist inside
  the home (mod directory or layout JSON); absent, broken, or escaping source
  paths fail the item. Do not recursively resolve personal ancestry. One
  warning may describe both a mismatch and unresolved ancestry. No findings
  yields an ok summary with the count of inspected clones and version basis.
  Zero clones is an explicit valid outcome only after a complete inventory.
  Never change provenance to silence warnings or call matching versions verified.

### Capability: sysup integration
Reuse the existing capability, rendering, and attention lifecycle.

#### Feature: Default audit and attention
- **Description**: Add an independently selectable audit alongside hmod.
- **Inputs**: Existing sysup selection/dry-run controls and capability registry.
- **Outputs**: Console-rendered results and the existing attention entry keyed
  by herdr-clones; no new state schema or configuration directory.
- **Behavior**: Register herdr-clone-audit with empty inputs. Add herdr-clones
  at order 79, use herdr-clone-audit, when `{os: darwin, check: herdr-app}`.
  Preserve herdr-mods at order 78 and its implementation. No running window is
  required. Use warned with success=True for review signals and failed with
  success=False for unusable input. The runner stamps command identity; existing
  attention persists all non-ok results, clears a completed clean audit, and
  retains unselected command entries. A mixed success/failure audit must retain
  the failure. Dry-run never enters the capability or reads Herdr files.
  Only adapters render; add no Click, output, or attention writes in the capability.

## Structural Decomposition

### Repository Structure

```text
src/tools/sysup/capabilities/herdr.py           # new provenance audit capability
src/tools/sysup/capabilities/__init__.py       # registry integration
src/tools/sysup/default.yaml                  # default audit entry
tests/tools/sysup/test_herdr.py                # new isolated audit tests
tests/tools/sysup/test_herdr_integration.py    # new runner/CLI attention tests
tests/tools/sysup/test_default_config.py       # existing plan assertions
docs/source/tools/sysup.rst                    # behavior and limitations
CHANGELOG.md                                  # unreleased feature entry
```

### Module: Herdr audit
- **Maps to capability**: Clone provenance audit
- **Location**: `src/tools/sysup/capabilities/herdr.py`, `tests/tools/sysup/test_herdr.py`
- **Responsibility**: Read confined metadata, query the CLI version, and yield findings.
- **Exports**: HerdrCloneAudit, implementing the existing Capability protocol.
- New symbols: `HerdrCloneAudit`, `src/tools/sysup/capabilities/herdr.py`, `tests/tools/sysup/test_herdr.py`.

### Module: sysup wiring
- **Maps to capability**: sysup integration
- **Location**: `src/tools/sysup/capabilities/__init__.py`, `src/tools/sysup/default.yaml`, `tests/tools/sysup/test_default_config.py`, `tests/tools/sysup/test_herdr_integration.py`
- **Responsibility**: Register the capability, schedule it, verify adapter behavior.
- **Exports**: Existing CAPABILITIES registration; no new interface-specific implementation.
- New symbols: `tests/tools/sysup/test_herdr_integration.py`.

### Module: User documentation
- **Maps to capability**: sysup integration
- **Location**: `docs/source/tools/sysup.rst`, `CHANGELOG.md`
- **Responsibility**: Explain selection, warnings, safe operation, and limitations.
- **Exports**: sysup reference and unreleased changelog entry.

## Dependency Graph

### Foundation Layer (Phase 0)
- **Herdr audit**: Depends on the existing Capability protocol and StepResult;
  no dependency on other unshipped PRDs, hmod internals, or a running app.

### Core Layer (Phase 1)
- **sysup wiring**: Depends on [Herdr audit]; reuse Runner and attention behavior.

### Integration Layer (Phase 2)
- **User documentation**: Depends on [Herdr audit, sysup wiring].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Deliver a read-only provenance audit with isolated tests.

**Tasks**:
- [ ] Implement HerdrCloneAudit and temporary-home tests for safe inventory, exact comparison, ancestry and failures (no deps). Acceptance: `uv run pytest tests/tools/sysup/test_herdr.py` covers every Critical Scenario below; all external calls are mocked and Herdr fixture bytes remain unchanged.

**Exit Criteria**: Audit emits accurate results without executing extension code.

### Phase 1: Core
**Goal**: Wire the audit into normal sysup runs and attention.

**Tasks**:
- [ ] Register the capability and add the default entry; update plan assertions additively (depends on: Phase 0). Premise: herdr-mods still runs hmod at order 78; re-check before editing, skip and report if ownership/order changed. Acceptance: `uv run pytest tests/tools/sysup/test_default_config.py` proves macOS order, Linux exclusion and existing hmod guards; preserve its named herdr-mods test.
- [ ] Add isolated CLI/runner integration tests using temporary attention storage (depends on: previous task). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_integration.py` proves warned attention/status with exit 0, failed audit with exit 1, clean clearing, mixed-result failure retention, unselected retention, and dry-run with no capability invocation.

**Exit Criteria**: Existing rendering and persistence handle all audit outcomes.

### Phase 2: Integration
**Goal**: Document the behavior and verify the completed change.

**Tasks**:
- [ ] Document `sysup --only herdr-clones`, HERDR_APP_HOME, disabling the entry through buvis-sysup.yaml, and the warned/failed distinction; add the unreleased changelog entry (depends on: Phase 1). Include explicit CLI-version basis, zero-clone behavior, unresolved ancestry, no compatibility guarantee, no live-window requirement, and deferred update/porting scope. Acceptance: `uv run sphinx-build -b html docs/source docs/build/html` succeeds; `rg -c "herdr-clones|HERDR_APP_HOME" docs/source/tools/sysup.rst` prints at least 2 and `rg -n "herdr-clones" CHANGELOG.md` hits.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass;
normal platform-dependent snapshot skips apply. Do not run updates as validation.

## Test Strategy

### Critical Scenarios
- **Happy path**: Direct shipped-source mod and layout clones match the CLI version; ok summary counts both, no attention remains after CLI execution.
- **Review signals**: Different versions, clone-of-clone, absent personal parent, and same-version unresolved ancestry warn. Versions such as 0.1.9 and 0.1.10 use exact comparison only. Warning text names the version basis without asserting incompatibility.
- **Empty inventory**: Valid directories/manifest with no clones report zero; optional missing mod.json is ignored. Hidden layout state is not inspected.
- **Invalid metadata**: Malformed JSON, nonobject documents, null/nonobject cloned_from, empty/nonstring fields, traversal names, unreadable files/directories, and invalid/missing installed.json fail without an all-clear.
- **Path confinement**: External/broken symlinks in roots, manifests, candidates or shipped source paths fail before reading outside the home; valid links within the home work.
- **Unavailable version**: Missing executable, OSError, timeout, nonzero exit, empty/extra-token output fail; no fabricated version or fallback to clone metadata.
- **Isolation**: Only the version subprocess is called; no status, do, check, hmod, agents, network, or Herdr writes. Closed-window operation succeeds with valid disk fixtures.
- **Lifecycle**: Failure and warning in one audit remain visible despite other matching clones; a later wholly clean audit clears attention; unrelated selections and dry-run do not erase prior attention.

## Risks

- **Version noise**: Matching release strings do not certify compatibility; differing strings do not prove a source changed. This is a review reminder only.
- **Binary/assets mismatch**: CLI version is not a running-window or generated-assets version. State that limitation; never promise an upgrade result.
- **Upstream schema changes**: Fail visibly on unsupported metadata and cover known shapes with minimal fixtures. No dependence on machine-local files in tests.
- **Concurrent changes**: A disappearing/unreadable input fails that item. This read-only inventory is not a transactional snapshot or a safe merge baseline.

---
catchup: force
eligibility: test -f docs/dev/project-management/prds/done/00157-sysup-herdr-bridge-v1.md
default_model: opus
model_tier_rationale: Durable content identity, concurrent storage admission and provenance contracts cross module boundaries.
---

# sysup Herdr snapshots and provenance

Source: `docs/dev/project-management/intake/processed/00157-sysup-herdr-update-orchestration/discovery.md` and sibling decisions.md.
Depends on PRD 00157's shared Herdr command facade; no update execution in this slice.

## Overview

### Problem Statement
Herdr replaces shipped assets at startup. Clone metadata records a version,
not trustworthy ancestry; a release tag cannot recreate a missing personal
parent. Preserve observed bytes and explicit accepted baselines without
claiming that every historical version has been captured.

### Target Users
The solo developer preserving personal Herdr mods and layouts before updates.

### Success Metrics
Tests prove immutable content identities, per-home separation, rejection of
unknown ancestry, bounded storage and retained references across failures.
No capture/adoption operation edits a live clone or changes cloned_from.

## Functional Decomposition

### Capability: Immutable source storage
Store only selected assets and enough evidence to distinguish observation from ancestry.

#### Feature: Capture and identity
- **Description**: Capture current source mods/layouts into a private store.
- **Inputs**: Canonical home; explicit asset kind/name or all shipped assets
  named in validated installed.json; observed app version with its basis.
  Home layout: mods/NAME/ directories, layouts/NAME.json files, and an
  installed.json object whose plain keys are shipped mods and whose
  layout:NAME keys are shipped layouts. The CLI version is the token in the
  output `herdr-app VERSION` of `herdr-app --version`.
- **Outputs**: Version-one manifests containing canonical home, kind/name,
  capture time, version/basis, sorted relative file paths, byte lengths,
  executable bits and SHA-256 content hashes; snapshot ID hashes the canonical
  content manifest, excluding capture time and version observations.
- **Behavior**: Store under XDG_STATE_HOME/sysup/herdr/HOME_HASH (fallback
  ~/.local/state), where HOME_HASH is SHA-256 of the canonical absolute home.
  Private directories 0700 and files 0600; preserve executable intent in metadata.
  Capture confined regular files/directories only, reject all symlinks and
  special files, omit .git internals, reject traversal and ambiguous names.
  A layout captures its JSON source, not layout click state or shared.json.
  Validate source before/after capture and abort on a changing tree. Stream
  hashing; do not buffer arbitrary files into memory. Atomic publication must
  never expose partial manifests/blobs. Verify digest integrity on reuse.
  Write manifests and ledger records with `atomic_write_text(path, text,
  mode=0o600)`. Blobs need a streaming publish local to the store (0600
  temporary file in the store, chunked hash, fsync, `os.replace`), because
  `atomic_write_bytes` makes 0644 files and holds the payload in memory.
  Do not edit `src/lib`.
  Label captured bytes observed, never authenticated shipped release content.
  If no running app is observed, record CLI-version basis explicitly.

#### Feature: Serialization and storage budget
- **Description**: Bound retained and temporary data without silently pruning history.
- **Inputs**: Per-home budget_bytes, positive integer default 1073741824,
  read from herdr.budget_bytes in the existing buvis-sysup.yaml configuration.
- **Outputs**: Admission result, store usage and explicit collection report.
- **Behavior**: Use one OS-held exclusive home lock, released on interruption
  and process death. Use `fcntl.flock` as `src/tools/klyreon/run/lock.py` does,
  without importing that module; import fcntl inside the lock code. Ten-second bounded lock acquisition; busy is a diagnostic.
  Expose a lock context so future update/port workflows can hold it across
  multiple store calls without recursive locking. Count all owned persistent
  source, candidate, journal and rollback bytes. Reserve expected incremental
  bytes and staging before copying; abort if streamed growth exceeds admission.
  No automatic deletion. Collection defaults to reporting; explicit apply
  rescans references under lock. Baselines, pending candidates and rollback
  records pin their inputs. Unknown schema/corrupt reference blocks collection.
  Never follow a store symlink or collect unrelated files. Failed staging is
  cleaned; crash remnants remain accounted and recoverable/collectable.
  Existing over-budget stores stay readable but refuse new allocations.
  External editor writes are not filesystem-quota controlled. Re-account editable
  workspaces on import and before admission; over-budget content blocks progress.

### Capability: Explicit baseline acceptance
Provide an honest foundation for later three-way ports.

#### Feature: Adoption and reference ledger
- **Description**: Bind a reviewed clone digest to a chosen future source baseline.
- **Inputs**: Asset kind/name, source snapshot ID, current reviewed clone digest,
  nonempty operator rationale and explicit adopt action.
- **Outputs**: Atomic version-one accepted-baseline record linking home, clone,
  source identity/digest, reviewed clone digest, timestamp and basis=user-adopted.
- **Behavior**: Verify home and asset identity, all referenced hashes and live
  clone digest under the home lock. Refuse changed or missing inputs. Adoption
  makes no historical-ancestry claim and never rewrites live metadata. A future
  successful port can record basis=ported with its predecessor and operation ID.
  Expose safe get/register/release reference operations for pending candidates
  and rollback records. Raw release-tag content is only a candidate source;
  never accept it solely because cloned_from.version matches a tag.

### Capability: Shared commands
Expose storage operations without adding an independent updater.

#### Feature: Snapshot, adoption and collection adapters
- **Description**: Extend sysup herdr with snapshot, adopt and gc operations.
- **Inputs**: Existing configuration context and explicit operator arguments.
- **Outputs**: CommandResult values with identities, usage, refusals and next steps.
- **Behavior**: CLI delegates to the same facade as other interfaces. Snapshot
  accepts kind/name or --all-shipped. Adopt requires source ID, clone digest
  and rationale. gc reports by default and mutates only with --apply.
  Do not fetch upstream repositories, execute mods, launch agents or update Herdr.
  Config stays in buvis-sysup.yaml; use the shared loader's machine-local policy.
  Define a typed optional herdr config section with that default; all facade
  operations receive the resolved budget, honoring --config and --config-dir.

## Structural Decomposition

### Repository Structure

```text
src/tools/sysup/herdr/store.py                 # immutable snapshots and references
src/tools/sysup/herdr/locking.py               # per-home OS lock
src/tools/sysup/commands/herdr.py              # extend shared facade from 00157
src/tools/sysup/config.py                      # typed budget configuration
src/tools/sysup/default.yaml                   # default storage budget
src/tools/sysup/cli.py                         # lazy storage adapters
tests/tools/sysup/test_herdr_store.py           # content/retention fault tests
tests/tools/sysup/test_herdr_locking.py         # process and interruption cases
tests/tools/sysup/test_herdr_commands.py        # extend facade/CLI assertions
tests/tools/sysup/test_config.py               # budget validation
docs/source/tools/sysup.rst                    # capture/adoption/collection
CHANGELOG.md                                  # unreleased entry
```

### Module: Store and lock
- **Maps to capability**: Immutable source storage; Explicit baseline acceptance
- **Responsibility**: Confine, admit, publish and retain content with honest provenance.
- **Exports**: HerdrStore, HerdrHomeLock. A test file that nears 800 lines may be split into `test_herdr_store_*.py` siblings; the acceptance commands then name each file.
- New symbols: `HerdrStore`, `HerdrHomeLock`, `src/tools/sysup/herdr/store.py`, `src/tools/sysup/herdr/locking.py`, `tests/tools/sysup/test_herdr_store.py`, `tests/tools/sysup/test_herdr_locking.py`.

### Module: Configuration and commands
- **Maps to capability**: Shared commands
- **Responsibility**: Read typed budget settings and adapt shared operations.
- **Exports**: Existing configuration and CommandHerdr facade from PRD 00157.
- New symbols: `CommandHerdr`, `src/tools/sysup/commands/herdr.py`, `tests/tools/sysup/test_herdr_commands.py` (created by prerequisite PRD 00157).

## Dependency Graph

### Foundation Layer (Phase 0)
- **Store and lock**: Existing atomic persistence; no live runtime needed.

### Core Layer (Phase 1)
- **Store and lock** (baseline and reference ledger): Depends on [Store and lock] capture and admission from Phase 0.

### Integration Layer (Phase 2)
- **Configuration and commands**: Depends on [Store and lock, PRD 00157].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Establish confined, bounded, durable storage.

**Tasks**:
- [ ] Implement per-home lock and content capture (no deps). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_locking.py tests/tools/sysup/test_herdr_store.py` proves cross-process exclusion, KeyboardInterrupt release, content identity, atomic failures and confinement.
- [ ] Add admission accounting, protected-reference collection and budget validation (depends on: previous task). This task adds the typed herdr section (field budget_bytes) to SysupConfig in `src/tools/sysup/config.py` and the key in `src/tools/sysup/default.yaml` in one commit, because SysupConfig refuses unknown keys; Phase 2 only passes the resolved value to the facade and CLI. Acceptance: `uv run pytest tests/tools/sysup/test_herdr_store.py tests/tools/sysup/test_config.py` covers capacity at/below/above limit, stream growth, staging remnants, invalid limits and corrupt-reference refusal.

**Exit Criteria**: Failures cannot publish incomplete content or evict referenced history.

### Phase 1: Core
**Goal**: Record future baselines without fabricating history.

**Tasks**:
- [ ] Implement digest-bound adoption and reference lifecycle (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_store.py` proves changed-clone refusal, adopted/ported basis distinction, missing/corrupt input refusal and unchanged live metadata.

**Exit Criteria**: Every accepted baseline and retained reference resolves to verified bytes.

### Phase 2: Integration
**Goal**: Expose usable commands and document the limits.

**Tasks**:
- [ ] Extend facade, CLI and config, preserving current defaults (depends on: Phase 1, PRD 00157). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_commands.py tests/tools/sysup/test_config.py` verifies identical command outcomes across facade and CLI, gc preview/apply separation and no hidden live mutation.
- [ ] Document baseline adoption, storage cap, explicit collection and missing history; add changelog (depends on: previous task). Do not name a machine-local config file; refer to the "Sharing across machines" section. Rename the example entry `herdr:` in the YAML quoting example of `docs/source/tools/sysup.rst`, so that it cannot be read as the new top-level herdr section. Acceptance: `uv run sphinx-build -b html docs/source docs/build/html` succeeds.

**Exit Criteria**: `uv run pytest` and `uv run mypy src/lib/ src/tools/` pass with normal platform snapshot skips.

## Test Strategy

### Critical Scenarios
- **Happy path**: Same source bytes captured twice → one content identity with separate observations; adopted baseline pins source.
- **Unknown ancestry**: Missing personal parent or tag-only evidence → no inferred baseline; explicit adoption records only a future basis.
- **Faults**: ENOSPC, interrupted publication, corrupt blob/reference, tree growth, symlink and concurrent writer → no partial accepted record or destructive collection.
- **Retention**: Pending candidate/rollback inputs remain pinned; unreferenced blobs collect only after explicit apply and fresh locked scan.
- **Isolation**: Different canonical homes are separate; aliased paths to the same home share a lock/store; live files remain unchanged.

## Risks

- **Unobserved upgrades**: This store cannot recover bytes never captured; expose missing baselines.
- **External editors**: Before/after checks detect changes but do not lock unrelated applications; require quiescent sources for meaningful capture.
- **Disk exhaustion**: Reservation enforces the configured budget, not free-space guarantees; atomic error handling remains mandatory.

---
default_model: opus
model_tier_rationale: Async command delivery, freshness deadlines and shared state require concurrency reasoning.
---

# sysup Herdr observation bridge

Source: `docs/dev/project-management/intake/processed/00157-sysup-herdr-update-orchestration/discovery.md` and sibling decisions.md.
Reference only: `docs/dev/project-management/spikes/herdr-update-bridge/RESULTS.md`.
Rebuild production code; the disposable spike must not become an installed asset.
Keep the spike directory in this PRD: PRD 00159 cites its RESULTS.md.

## Overview

### Problem Statement
Herdr can start updates through its CLI but exposes completion state only to
loaded mods. Provide a local observation adapter without an upstream dependency.
The isolated Herdr 0.1.16 experiment proved fresh persisted replies, quit/relaunch
recovery, absence detection and layout restoration. It did not install an update.

### Target Users
The solo developer who wants sysup to observe Herdr safely.

### Success Metrics
Fixture tests reject every stale, malformed, absent and timed-out response.
The packaged bridge is installable without overwriting personal files or layouts.
No observation command starts updates, agents, terminals or application restarts.

## Functional Decomposition

### Capability: Fresh update observation
Expose the documented mod API through Herdr's supported command delivery.

#### Feature: Loaded bridge
- **Description**: Package a small visible mod named sysup-probe.
- **Inputs**: Custom command probe- followed by 32 lowercase hexadecimal digits.
- **Outputs**: One mod-owned shared value keyed sysup.update-probe:
  schema integer 1, nonce string, state object containing app, core, checked,
  checks and checking from updates(); omit release notes (its notes member).
- **Behavior**: Use init(props, cx), the spawned task's context, nextCommand,
  setShared and updates. Check mode does nothing. Validate the complete command
  before sampling. Notify the task context after awaiting to stop obsolete
  instances. Render a small status label. No filesystem access, network calls,
  update actions or subprocesses in the mod. Herdr owns shared.json persistence.
  Exact Herdr 0.1.16 API, as exercised by the spike's `main.js`: import View and
  div from gpui-kit; import checking, nextCommand, setShared and updates from
  herdr. The default export extends View and defines init(props, cx) and render().
  checking() returning true is check mode. cx.spawn(async (taskCx) => ...) starts
  the loop; await nextCommand() yields the command text after the mod prefix;
  call taskCx.notify() after each await; setShared(key, value) stores the reply.
  mod.json holds the JSON object `{"place": "none"}`; the packaged bytes are the
  reference for the identical-reinstall check. The mod directory name is the
  command prefix, so the directory must be sysup-probe.

#### Feature: Bounded client
- **Description**: Return a fresh typed state sample or an unavailable reason.
- **Inputs**: Canonical Herdr home; herdr-app executable; five-second default
  probe deadline, positive and finite; injected clock/process/file adapters.
- **Outputs**: HerdrObservation with available flag, validated state or reason.
- **Behavior**: Generate a new cryptographically random 128-bit nonce per probe.
  Run herdr-app do sysup-probe.probe-NONCE without a shell, with the selected
  HERDR_APP_HOME. Poll that home's shared.json every 50 ms within one monotonic
  deadline covering dispatch and reads. shared.json is one JSON object; the reply
  is its top-level sysup.update-probe member. Accept only matching schema and nonce.
  Require app version nonempty string; app ready nullable string and updates
  boolean; core version/managed/ready/error nullable strings and updating boolean;
  checked null or finite nonnegative number; checks/checking booleans. Reject
  booleans as numbers. Ignore extra fields; missing required fields fail.
  The Herdr 0.1.16 type of updates() (herdr.d.ts, read 2026-11-17) is
  `{app: {version: string; ready: string | null; updates: boolean}; notes: [...];
  core: {version: string | null; managed: string | null; ready: string | null;
  updating: boolean; error: string | null}; checked: number | null;
  checks: boolean; checking: boolean}`.
  Reject unsupported schema, malformed matching payload or escaping paths.
  Retry transient missing/partially-written state only until deadline. While the
  CLI answers unknown command (the mod is not loaded yet, for example just after
  a start), send the same nonce again every 50 ms until the deadline, as the
  spike's native_probe.py does. At the deadline, unknown
  command, closed app, timeout and launch errors mean unavailable, never cached
  success. Do not write shared.json. Limit reads to 1 MiB; oversized files fail
  with a diagnostic. This is same-user observation, not an authentication channel.

### Capability: Explicit setup
Install owned assets and expose the shared command service.

#### Feature: Installation and probe commands
- **Description**: Add sysup herdr bridge install and sysup herdr probe.
- **Inputs**: Existing sysup configuration context and selected Herdr home.
- **Outputs**: CommandResult values; CLI renders through console.
- **Behavior**: Installation creates only mods/sysup-probe with private staging
  and atomic publication; identical packaged content is a no-op. The library
  has no directory helper: stage a sibling directory under mods/ and rename it
  onto the absent target. Refuse any
  existing different content, symlink or collision; provide manual resolution.
  Do not edit a layout, launch the app or run mod checks. Give exact instructions
  to load one block in a personal layout using Herdr's supported layout editor.
  The block is `{"type": "block", "id": "sysup-probe", "content": {"mod": "sysup-probe"}}`.
  Probe calls the same client available to future TUI/API/WebUI adapters.
  Resolve HERDR_APP_HOME or ~/.config/herdr-app; reject empty override and
  confine every derived path. Normal sysup runs install nothing.
  Ensure wheel packaging includes main.js and mod.json.

## Structural Decomposition

### Repository Structure

```text
src/tools/sysup/herdr/__init__.py              # shared observation exports
src/tools/sysup/herdr/bridge.py                # protocol and bounded client
src/tools/sysup/herdr/assets/main.js           # new production bridge
src/tools/sysup/herdr/assets/mod.json          # bridge manifest
src/tools/sysup/commands/__init__.py           # new command package exports
src/tools/sysup/commands/herdr.py              # shared CommandResult facade
src/tools/sysup/cli.py                         # lazy CLI adapters
tests/tools/sysup/test_herdr_bridge.py          # client and install cases
tests/tools/sysup/test_herdr_bridge_mod.mjs     # exact packaged source harness
tests/tools/sysup/test_herdr_commands.py        # adapter and wheel assertions
tests/tools/sysup/test_sysup_cli.py             # pinned subcommand set gains herdr
docs/source/tools/sysup.rst                    # setup and limitations
CHANGELOG.md                                  # unreleased entry
```

### Module: Observation
- **Maps to capability**: Fresh update observation
- **Responsibility**: Package the bridge and validate bounded fresh samples.
- **Exports**: HerdrObservation, HerdrBridge.
- New symbols: `HerdrObservation`, `HerdrBridge`, `src/tools/sysup/herdr/__init__.py`, `src/tools/sysup/herdr/bridge.py`, `src/tools/sysup/herdr/assets/main.js`, `src/tools/sysup/herdr/assets/mod.json`, `tests/tools/sysup/test_herdr_bridge.py`, `tests/tools/sysup/test_herdr_bridge_mod.mjs`.

### Module: Commands and documentation
- **Maps to capability**: Explicit setup
- **Responsibility**: Install owned assets, expose observation, render only in adapters.
- **Exports**: CommandHerdr; existing sysup CLI and reference documentation.
- New symbols: `CommandHerdr`, `src/tools/sysup/commands/__init__.py`, `src/tools/sysup/commands/herdr.py`, `tests/tools/sysup/test_herdr_commands.py`.

## Dependency Graph

### Foundation Layer (Phase 0)
- **Observation**: Existing atomic persistence and CommandResult conventions;
  no unshipped PRD dependency. Pinned installed API is the reference, not a runtime dependency on this workstation.

### Core Layer (Phase 1)
- **Commands and documentation**: Depends on [Observation].

### Integration Layer (Phase 2)
- **Commands and documentation** (packaging proof and reference docs): Depends on [Observation].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Implement the observed protocol independently of the disposable spike.

**Tasks**:
- [ ] Implement packaged bridge and exact-source harness (no deps). Read `docs/dev/project-management/spikes/herdr-update-bridge/main.js` and `docs/dev/project-management/spikes/herdr-update-bridge/probe.mjs` for the verified API shapes; the harness mocks exactly the Loaded bridge API listed above and calls init(undefined, cx), so a mod that reads its context from the first argument fails. Acceptance: `node --test tests/tools/sysup/test_herdr_bridge_mod.mjs` proves real init argument order, check-mode silence, full nonce matching, one taskCx.notify() call after each awaited command, and simulated instance replacement (a reply from an old instance never satisfies a new nonce). The harness does not model how Herdr stops an obsolete instance; the spike did not record that.
- [ ] Implement bounded typed client (depends on: previous task). Add one pytest case in `tests/tools/sysup/test_herdr_bridge.py` that runs the Node harness as a subprocess and skips only when node is not on PATH, so `uv run pytest` covers the mod wherever node is installed (the CI tools job installs no node; report a skip as a skip). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_bridge.py` covers stale/unloaded/restarted/malformed/oversized states with fake clocks and no live home access, and runs the Node harness case.

**Exit Criteria**: Only a matching fresh validated reply is available.

### Phase 1: Core
**Goal**: Provide explicit installation and shared commands.

**Tasks**:
- [ ] Implement CommandHerdr install/probe operations and lazy CLI adapters (depends on: Phase 0). Acceptance: `uv run pytest tests/tools/sysup/test_herdr_commands.py` verifies CommandResult parity, unchanged layouts, collision refusal, identical reinstall, confinement and console rendering. Update `test_cli_is_a_group_with_status_and_refresh` in `tests/tools/sysup/test_sysup_cli.py` to expect the set `{"herdr", "refresh", "status"}`.

**Exit Criteria**: Installing files does not claim the bridge is loaded.

### Phase 2: Integration
**Goal**: Ship usable setup and packaged assets.

**Tasks**:
- [ ] Document setup, absent-block recovery, five-second timeout, same-user trust and scope; add changelog (depends on: Phase 1). Acceptance: `uv run sphinx-build -b html docs/source docs/build/html` succeeds.
- [ ] Verify a built wheel contains both assets through a focused packaging assertion in `tests/tools/sysup/test_herdr_commands.py` (depends on: Phase 1). Follow the opt-in pattern of `tests/tools/klyreon/assets/test_wheel_resolution.py`: the test runs only with BUVIS_WHEEL_BUILD_TESTS=1, builds with `uv build --wheel` under BUVIS_SKIP_FRONTEND=1, and skips when the build toolchain is unavailable; an always-on wheel build crashes the CI interpreter. Acceptance: `BUVIS_WHEEL_BUILD_TESTS=1 uv run pytest tests/tools/sysup/test_herdr_commands.py -k wheel` reads the wheel, never the source tree, and fails if `sysup/herdr/assets/main.js` or `sysup/herdr/assets/mod.json` is missing; report a skip as a skip.

**Exit Criteria**: `uv run pytest`, `uv run mypy src/lib/ src/tools/` and the Node harness pass; normal platform snapshot skips apply. No live GUI is required in CI.

## Test Strategy

### Critical Scenarios
- **Happy path**: Command accepted, delayed flush, exact nonce → validated state.
- **Lifecycle**: Old response after restart/unload → unavailable until a fresh reply; late old-instance writes never satisfy a new request.
- **Error case**: Closed window, unrecognized command, invalid schema/types, nonfinite numbers, oversized state, symlink escape and subprocess timeout → actionable unavailable reason.
- **Installation**: New, identical, edited and symlinked destinations → safe install, no-op, refusal and refusal respectively; no layout edits or live code execution.

## Risks

- **Upstream changes**: Build against the Herdr 0.1.16 API recorded in this PRD and the spike; do not read the workstation's Herdr home during the build. At runtime unsupported contracts fail visibly. Keep observation replaceable by a future supported CLI query.
- **Loaded-block requirement**: A different layout disables observation; explicit setup and diagnostics are essential.
- **Single response slot**: Future mutation workflows serialize per home. Independent probes can time out under contention but cannot accept another nonce.

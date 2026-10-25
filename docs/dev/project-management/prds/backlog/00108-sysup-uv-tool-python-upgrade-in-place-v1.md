---
catchup: skip
design: skip
ledger: deferred/202610242315-deferred.json
ledger_key: 59e94f9ea936
source_prd: 00105-sysup-uv-tool-python-pin-v1.md
default_model: sonnet
model_tier_rationale: transcription only - the two replacement function bodies, every argv, every message and every test receipt are given verbatim; a wrong edit breaks a named test
---

# sysup uv-tool-python: move customized uv tool installs with uv tool upgrade

Source: attended triage of hold stub `00106-triage-engram-gets-skipped-with-success-false-o-v1.md` on 2026-10-25 (ledger key `59e94f9ea936`, deferred HIGH from PRD 00105, batch 202610242315).

## Overview

### Problem Statement
`uv-tool-python` moves only "plain" uv tool installs. `_pinned_minor` raises `ValueError` for any receipt customization: an editable requirement, extras, a specifier, a URL, constraints, overrides, excludes, build constraints, non-empty options, an unknown key, an entrypoint from another package, or a receipt whose requirement name differs from the tool directory.
`src/tools/sysup/capabilities/uv_tool_python.py:42-91`
Every such tool yields `StepResult(success=False, message=f"{exc}, skipping")` on every run.
`src/tools/sysup/capabilities/uv_tool_python.py:135-141`

On this host the engram tool is an editable install (receipt requirement `{ name = "engram", editable = "<checkout path>" }`), so every `sysup` run ends red and exits 1 even when nothing else failed, and engram stays unpinned, which is the drift the capability exists to prevent. The skip was the only safe choice under the current reinstall mechanism: `_move` runs `uv tool install --python <target> --force <tool>` with the bare tool name, which would replace an editable checkout with the PyPI package and drop extras, specifiers and constraints.
`src/tools/sysup/capabilities/uv_tool_python.py:160-174`

### Target Users
The solo operator running `sysup`, whose freestanding uv tools include editable checkouts and tools installed with extras or constraints.

### Success Metrics
- `uv run pytest tests/tools/sysup/test_uv_tool_python.py -q` passes, including the new `test_moves_customized_receipts_in_place` and the narrowed `test_reports_unsafe_receipt_and_continues_without_reinstalling_it`.
- `uv run pytest tests/tools/sysup/test_invariants.py tests/tools/sysup/test_default_config.py -q` passes unchanged.
- `uv run mypy src/tools/sysup` and `uv run ruff check src/tools/sysup tests/tools/sysup/test_uv_tool_python.py` are clean.
- `rg -c "tool upgrade --python" docs/source/tools/sysup.rst` prints at least 1 and `rg -c '"install"' src/tools/sysup/capabilities/uv_tool_python.py` prints 1 (the remaining `uv python install` call only).

## Functional Decomposition

### Capability: Pin every freestanding uv tool to the global Python minor
Replace the plain-install reinstall with an in-place interpreter switch that keeps whatever the receipt recorded, and stop skipping receipts the new mechanism can handle.

#### Feature: Read the pinned minor from any well-formed receipt
- **Description**: `_pinned_minor` keeps the structural checks and drops the customization allowlist.
- **Inputs**: `<tool>/uv-receipt.toml`.
- **Outputs**: the pinned minor as `"X.Y"`, `None` when the receipt has no `python` key, `ValueError` for a malformed receipt.
- **Behavior**: the function body becomes exactly:

```python
def _pinned_minor(receipt_path: Path) -> str | None:
    with receipt_path.open("rb") as receipt:
        data = tomllib.load(receipt)
    tool = data.get("tool")
    if not isinstance(tool, dict):
        raise ValueError("missing tool table")
    requirements = tool.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("missing requirements")
    if "python" not in tool:
        return None
    selector = tool["python"]
    match = _VERSION.fullmatch(selector) if isinstance(selector, str) else None
    if match is None:
        raise ValueError(f"unsupported python selector: {selector!r}")
    return match.group(1)
```

  Removed on purpose: the allowed-keys set, the `options == {}` check, the single-requirement identity check, the extras/specifier emptiness checks, the `dependency_keys` emptiness check and the entrypoint-source check. `uv tool upgrade` reads all of those from the receipt itself, so the capability no longer needs to understand them. `_normalize` loses its last caller and is deleted.

#### Feature: Move tools with uv tool upgrade --python
- **Description**: `_move` switches the interpreter in place instead of force-reinstalling by name.
- **Inputs**: the uv binary, the tool directory name, the old minor or `None`, the target minor.
- **Outputs**: the same `StepResult` labels and messages as today.
- **Behavior**: the method body becomes exactly:

```python
    def _move(self: UvToolPython, uv: str, tool: str, old: str | None, target: str) -> StepResult:
        label = f"{tool} (python {old or 'unpinned'} -> {target})"
        error = _run_install([uv, "tool", "upgrade", "--python", target, tool])
        if error is None:
            return StepResult(label, success=True)
        rollback = [uv, "tool", "upgrade"]
        if old is not None:
            rollback.extend(["--python", old])
        recovery = _run_install([*rollback, tool])
        if recovery is None:
            state = f"kept on python {old}" if old else "kept unpinned"
        else:
            state = f"reinstall on python {old} also failed" if old else "unpinned reinstall also failed"
            state = f"{state}: {recovery}"
        return StepResult(label, success=False, message=f"{state}: {error}")
```

  The host uv (0.13.5) documents `-p, --python <PYTHON>` on `uv tool upgrade` as "Upgrade a tool, and specify it to use the given Python interpreter to build its environment"; the upgrade re-resolves from the receipt's recorded requirements, so an editable path, extras, specifiers, constraints and index options survive and the receipt records the new interpreter (unverified library claim). The `uv python install <target>` call before the loop stays as it is.

#### Feature: Keep malformed receipts visible
- **Description**: unreadable receipts still produce one red, labelled step and never stop the other tools.
- **Inputs**: `OSError`, `tomllib.TOMLDecodeError` or `ValueError` from `_pinned_minor`.
- **Outputs**: `StepResult(directory.name, success=False, message=f"{exc}, skipping")`, unchanged.
- **Behavior**: no change to the loop in `run`; only the set of receipts that raise shrinks to: unreadable file, invalid TOML, no `tool` table, no or empty `requirements` list, non-string or unparseable `python` selector.

## Structural Decomposition

### Repository Structure

```
src/tools/sysup/capabilities/uv_tool_python.py   # Maps to: Pin every freestanding uv tool (all three features)
tests/tools/sysup/test_uv_tool_python.py         # Maps to: all three features (fake uv, receipts)
docs/source/tools/sysup.rst                      # Maps to: capability table row and the order-35 paragraph
CHANGELOG.md                                     # Maps to: Fixed entry
```

### Module: uv-tool-python capability
- **Maps to capability**: Pin every freestanding uv tool to the global Python minor
- **Location**: `src/tools/sysup/capabilities/uv_tool_python.py`
- **Responsibility**: discover receipts, decide which tools move, run the move and its rollback.
- **Exports**:
  - `UvToolPython` - unchanged class and `inputs`
  - `_pinned_minor()` - the shortened reader above
  - `_move()` - the upgrade-based move above

### Module: uv-tool-python tests
- **Maps to capability**: Pin every freestanding uv tool to the global Python minor
- **Location**: `tests/tools/sysup/test_uv_tool_python.py`
- **Responsibility**: drive `UvToolPython.run` against a fake `uv` and `mise` and assert argv, labels, messages and untouched receipts.
- **Exports**: none (test module)
- New symbols: `test_moves_customized_receipts_in_place`

### Module: sysup docs and changelog
- **Maps to capability**: Pin every freestanding uv tool to the global Python minor
- **Location**: `docs/source/tools/sysup.rst`, `CHANGELOG.md`
- **Responsibility**: describe the new mechanism and its limits.
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **uv-tool-python tests**: the fake uv accepts the new argv; the new and narrowed tests fail against the current code.

### Core Layer (Phase 1)
- **uv-tool-python capability**: Depends on [uv-tool-python tests]

### Integration Layer (Phase 2)
- **sysup docs and changelog**: Depends on [uv-tool-python capability]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Tests that pin the upgrade-based move and the narrowed skip set.

**Tasks**:
- [ ] Update the fake and the existing expectations in `tests/tools/sysup/test_uv_tool_python.py` (no deps) - Acceptance: `_fake_run` accepts argv starting with `["/bin/uv", "tool", "upgrade"]` instead of `["/bin/uv", "tool", "install"]`; `_installs` filters on `["tool", "upgrade"]`; `test_pins_unpinned_tool_to_global_minor_and_reinstalls`, `test_moves_stale_pin_to_global_minor` and `test_reverts_to_prior_interpreter_when_tool_fails_on_new_minor` expect `["/bin/uv", "tool", "upgrade", "--python", <target>, <tool>]` for the move, `["/bin/uv", "tool", "upgrade", "--python", <old>, <tool>]` for a pinned rollback and `["/bin/uv", "tool", "upgrade", <tool>]` for an unpinned rollback; `test_reports_unsafe_receipt_and_continues_without_reinstalling_it` keeps only the receipts `""`, `"[tool"`, `'[other]\npython = "3.13"\n'`, `'[tool]\npython = "3.13"\n'`, `"[tool]\nrequirements = []\n"`, `'[tool]\nrequirements = ["gita"]\npython = 314\n'` and `'[tool]\nrequirements = ["gita"]\npython = false\n'` and expects the zulu move argv `["/bin/uv", "tool", "upgrade", "--python", "3.14", "zulu"]`. `uv run pytest tests/tools/sysup/test_uv_tool_python.py -q` fails against the current code on exactly those tests.
- [ ] Add `test_moves_customized_receipts_in_place` to the same file (no deps) - Acceptance: parametrized over the receipts that used to be skipped: `'[tool]\nrequirements = [{name = "gita", editable = "/src/gita"}]\n'`, `'[tool]\nrequirements = [{name = "gita", extras = ["web"]}]\n'`, `'[tool]\nrequirements = [{name = "gita", specifier = ">=1"}]\n'`, `'[tool]\nrequirements = [{name = "gita", url = "https://example.org/gita.whl"}]\n'`, `'[tool]\nrequirements = ["gita==1.0"]\n'`, `'[tool]\nrequirements = ["gita", "beets"]\n'`, `'[tool]\nrequirements = ["gita-extra"]\n'`, `'[tool]\nrequirements = ["gita"]\nconstraints = ["beets<2"]\n'`, `'[tool]\nrequirements = ["gita"]\noverrides = ["beets"]\n'`, `'[tool]\nrequirements = ["gita"]\nexcludes = ["beets"]\n'`, `'[tool]\nrequirements = ["gita"]\nbuild-constraint-dependencies = ["beets"]\n'`, `'[tool]\nrequirements = ["gita"]\noptions = {index = "https://example.org"}\n'`, `'[tool]\nrequirements = ["gita"]\nentrypoints = [{name = "gita", from = "gita-extra"}]\n'`, `'[tool]\nrequirements = ["gita"]\nfuture = []\n'`; each yields one step with label `gita (python unpinned -> 3.14)` and `success` True, the only tool argv is `["/bin/uv", "tool", "upgrade", "--python", "3.14", "gita"]`, and the receipt bytes are unchanged afterwards. The test fails against the current code.

**Exit Criteria**: the file collects, and only the tests named above fail.

### Phase 1: Core
**Goal**: The capability moves every well-formed receipt in place.

**Tasks**:
- [ ] Replace `_pinned_minor` and `_move` in `src/tools/sysup/capabilities/uv_tool_python.py` with the bodies given under the two features above and delete `_normalize` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/sysup/test_uv_tool_python.py -q` passes; `uv run mypy src/tools/sysup` and `uv run ruff check src/tools/sysup tests/tools/sysup/test_uv_tool_python.py` are clean; `rg -c '"install"' src/tools/sysup/capabilities/uv_tool_python.py` prints 1.

**Exit Criteria**: `uv run pytest -m sysup -q` passes.

### Phase 2: Integration
**Goal**: Docs and changelog describe the new mechanism.

**Tasks**:
- [ ] Update `docs/source/tools/sysup.rst` and `CHANGELOG.md` (depends on: Phase 1) - Acceptance: the capability table row reads ``moves every uv tool install to the global mise Python minor with ``uv tool upgrade --python``; no inputs``; the order-35 paragraph says that unpinned tools and tools with an older numeric pin are moved with ``uv tool upgrade --python <minor> <tool>``, which keeps the receipt's recorded requirements (an editable checkout, extras, constraints, index options) and only switches the interpreter, that equal and newer pins stay unchanged, that a failed move retries ``uv tool upgrade`` on the prior minor or without a pin and reports any rollback failure, and that only malformed or missing receipts and unsupported ``python`` selectors are skipped; `CHANGELOG.md` gains under `[Unreleased]` / `### Fixed` the line "- **sysup**: `uv-tool-python` now moves editable and otherwise customized uv tool installs with `uv tool upgrade --python`, so a host with an editable tool no longer ends every run red; only malformed receipts are skipped". `uv run sphinx-build -b html docs/source docs/build/html` succeeds and `rg -c "tool upgrade --python" docs/source/tools/sysup.rst` prints at least 1.

**Exit Criteria**: `uv run pytest`, `uv run mypy src/lib/ src/tools/` and `pre-commit run --all-files` pass once after all tasks.

## Test Strategy

### Critical Scenarios
- **Happy path**: an editable receipt without `python` on a host whose global minor is 3.14 → Expected: one green step `gita (python unpinned -> 3.14)` and the argv `uv tool upgrade --python 3.14 gita`.
- **Edge case**: a receipt with extras, constraints and an unknown key, pinned to 3.12 → Expected: moved with the same upgrade argv; the receipt file is not rewritten by sysup.
- **Edge case**: a receipt pinned to 3.15 on a 3.14 host → Expected: untouched, summary `all uv tools pinned to python 3.14 or newer` (unchanged behavior).
- **Error case**: the upgrade on 3.14 fails for a tool pinned to 3.12 → Expected: rollback `uv tool upgrade --python 3.12 <tool>`, red step `kept on python 3.12: <error>`.
- **Error case**: invalid TOML or a `python = 314` selector → Expected: red step `<tool>: <reason>, skipping`, the other tools still move.

## Risks
- **`uv tool upgrade` bumps package versions as well as the interpreter**: accepted; the very next sysup step is `uv tool upgrade --all`, so nothing is upgraded earlier than it would be anyway.
- **An upgrade that fails mid-install leaves a half-built environment**: the rollback upgrade on the prior interpreter restores a consistent environment, as the force-reinstall rollback did; an unpinned rollback still cannot promise the original interpreter, and the docs keep saying so.
- **The receipt format gains keys**: no longer a risk; the reader looks only at `tool`, `requirements` and `python`.

---
default_model: sonnet
model_tier_rationale: a single new capability that mirrors an existing one (PipxPython) in shape, idiom and tests; the pure logic (parse receipts, pick the global minor, reinstall with --python, revert on failure) is transcribed from a working sibling rather than invented, and the wiring is one `use:` entry in default.yaml
---

# sysup uv-tool-python: pin freestanding uv tools to the global python minor

Source: discovered 2026-10-24 from a sysup run failure. `uv tool upgrade --all` tried to resolve `mempalace` against CPython 3.15 (the newest uv-managed interpreter after a Homebrew `python@3.15` landed), where `onnxruntime` (a transitive dep via `chromadb`) has no `cp315` wheel, so the whole resolution was unsatisfiable and the uv step failed. The immediate drift was fixed by hand (`uv tool install --python 3.14 --force mempalace`, receipt now records `python = "3.14"`), but nothing in sysup prevents recurrence for `mempalace` or any other freestanding uv tool.

## Overview

### Problem Statement
sysup keeps mise `pipx:` tools on a known-good python minor through the `pipx-python` capability (`src/tools/sysup/capabilities/pipx_python.py`, wired at `order: 65` in `default.yaml`): it reads each `--managed-python --python X.Y` pin, moves any stale one to the global mise python minor, reinstalls, and reverts a tool that fails to build on the new minor.

Freestanding `uv tool` installs get no such guard. The uv step is just `[uv, python, upgrade]` then `[uv, tool, upgrade, --all]` (`default.yaml:36-37`). `uv tool upgrade` resolves each tool against the interpreter recorded in its receipt (`~/.local/share/uv/tools/<tool>/uv-receipt.toml`); a tool installed without `--python` has no `python` key in the receipt and re-resolves against the newest uv-managed interpreter available. When a new CPython minor lands (here 3.15 via Homebrew) before the native-wheel ecosystem catches up, an unpinned tool with a compiled transitive dep (`onnxruntime`, `tokenizers`, ...) becomes unsatisfiable, and `uv tool upgrade --all` fails for the whole batch.

The host currently has three freestanding uv tools (`uv tool list`: `engram`, `huggingface-hub`, `mempalace`); `mempalace` and `engram` both pull compiled deps, so this is not a one-tool accident.

This PRD adds a sysup capability that, before `uv tool upgrade --all` runs, pins every freestanding uv tool whose receipt has no `python` key (or a stale minor) to the global mise python minor and reinstalls it, reverting any tool that fails to build on that minor to its prior interpreter — the exact safety contract `pipx-python` gives mise tools.

### Target Users
The solo operator running `sysup` by hand or from a scheduler, whose uv-tool upgrades must survive a new CPython minor landing before compiled wheels exist for it.

### Success Metrics
- `uv run pytest tests/tools/sysup/test_uv_tool_python.py -q` passes: `test_pins_unpinned_tool_to_global_minor_and_reinstalls`, `test_moves_stale_pin_to_global_minor`, `test_leaves_current_pin_untouched`, `test_reverts_to_prior_interpreter_when_tool_fails_on_new_minor`, `test_no_tools_is_a_noop`, `test_no_global_python_skips`, `test_missing_uv_or_mise_skips`.
- `uv run pytest tests/tools/sysup/test_default_config.py -q` passes with a new assertion that `uv-tool-python` is wired at an order between the `uv` entry and `mise`'s downstream steps, guarded by `when: { os: darwin, check: uv }`.
- `uv run pytest tests/tools/sysup/test_invariants.py -q` passes: it globs `capabilities/*.py` (`test_invariants.py:18`), so the new `uv_tool_python.py` is covered automatically and must satisfy the "yields `StepResult` or raises" contract.
- `uv run pytest -m sysup -q` passes; `uv run mypy src/tools/sysup` and `uv run ruff check src/tools/sysup tests/tools/sysup/test_uv_tool_python.py` clean.
- `rg -c "uv-tool-python\|freestanding uv tool" CHANGELOG.md` prints at least 1.

## Functional Decomposition

### Capability: Pin freestanding uv tools to the global python minor
Before the uv upgrade step re-resolves them, every freestanding `uv tool` is anchored to a python minor the mise global already uses, so an upgrade never drifts to an interpreter without wheels.

#### Feature: Discover installed uv tools and their recorded python
- **Description**: Enumerate the tools under the uv tools directory and read the interpreter each receipt pins (if any).
- **Inputs**: the uv tools dir (`uv tool dir` output, fallback `$XDG_DATA_HOME/uv/tools` then `~/.local/share/uv/tools`); each tool's `uv-receipt.toml`.
- **Outputs**: a list of `(tool_name, pinned_minor_or_none)`.
- **Behavior**: `uv tool dir` gives the root; each immediate subdirectory is a tool. The receipt's `[tool]` table may hold a `python` key (a version or minor string, e.g. `"3.14"`); its minor (`^(\d+\.\d+)`) is the pinned minor, `None` when the key is absent. Tools are read-only here; nothing is written during discovery. Parsing uses `tomllib` (stdlib, 3.11+), already the project baseline.

#### Feature: Move each tool onto the global minor
- **Description**: A tool with no pin, or a pin below the global mise python minor, is reinstalled pinned to that minor; a tool already on it is left alone.
- **Inputs**: the discovered `(tool, pinned)` list, the global mise python minor (`mise current python` run from `$HOME`, minor only), the resolved `uv` and `mise` binaries.
- **Outputs**: one `StepResult` per tool actually moved (`<tool> (python <old> -> <target>)`, `old` is the prior minor or `unpinned`); a single `ok` result `all uv tools on python <target>` when nothing needs moving.
- **Behavior**: mirrors `PipxPython`. `uv python install <target>` once up front; then for each stale tool `uv tool install --python <target> --force <tool>`. On success, the receipt now records the target. On failure, reinstall at the prior interpreter — `uv tool install --python <old> --force <tool>` when it had a pin, else `uv tool install --force <tool>` (no `--python`, restoring the unpinned state) — and report the step failed with `kept on python <old>` / `kept unpinned` plus the captured stderr, so one bad wheel never leaves a tool broken. A tool already on the target minor is skipped (no reinstall call).
- **Guards**: `uv` or `mise` missing -> one `ok`-framed skip result `uv or mise not found, skipping` (not a failure, matching `pipx-python`'s "skipping" wording is `success=False`; re-decided here as `success=False` to stay identical to the sibling). No global mise python minor -> `success=False`, `no global mise python version, skipping`. No tools at all -> one `ok` result `no uv tools installed`.

#### Feature: Wire the capability before the uv upgrade
- **Description**: A `default.yaml` entry runs this capability before `uv tool upgrade --all` re-resolves the tools.
- **Inputs**: the command table in `src/tools/sysup/default.yaml`.
- **Outputs**: a new `uv-tool-python` command entry.
- **Behavior**: the `uv` entry (`order: 40`) runs `[uv, python, upgrade]` then `[uv, tool, upgrade, --all]`. The new entry must pin BEFORE that upgrade, so it either (a) becomes `order: 35` running ahead of `uv`, or (b) the `uv` entry's steps are split so pinning sits between `uv python upgrade` and `uv tool upgrade --all`. Decided at create-prd: option (a) — a separate `uv-tool-python` entry at `order: 35`, `when: { os: darwin, check: uv }`, `use: uv-tool-python` — keeps the capability independently skippable and testable and leaves the `uv` entry's two-step shape untouched. `uv python upgrade` (patch-level bumps of already-installed minors) at `order: 40` does not install new minors, so running the pin at 35 against the current global minor is correct; the pin targets the mise global minor, not whatever `uv python upgrade` might touch.

## Structural Decomposition

### Repository Structure

```
src/tools/sysup/
├── capabilities/
│   └── uv_tool_python.py           # NEW: Maps to: Pin freestanding uv tools to the global python minor
├── capabilities/__init__.py        # register UvToolPython under the "uv-tool-python" use-name
└── default.yaml                    # NEW uv-tool-python entry at order 35
tests/tools/sysup/
├── test_uv_tool_python.py          # NEW
├── test_default_config.py          # assertion: uv-tool-python wired, order, guard
└── test_invariants.py              # auto-globs capabilities/*.py; new module covered, no edit
docs/source/tools/sysup.rst         # Attention/Configuration note on uv-tool pinning
CHANGELOG.md                        # Added entry
```

### Module: sysup.capabilities.uv_tool_python
- **Maps to capability**: Pin freestanding uv tools to the global python minor
- **Responsibility**: Discover uv tools, read their receipts, move stale/unpinned ones onto the global mise python minor, revert a tool that fails to build. No console output beyond yielded `StepResult`s; no process exit. Pure helpers (`_pinned_minor`, `_global_minor`, `_tool_dir`) separated from the `subprocess`-driven `run`.
- **Exports**: `UvToolPython`
- New symbols: `UvToolPython`, `_pinned_minor`, `_tool_dir`, `_global_minor`, `uv_tool_python.py`

### Module: sysup.capabilities (registry)
- **Maps to capability**: Wire the capability
- **Responsibility**: register `UvToolPython` under the `use:` name `uv-tool-python`, the same way `PipxPython` is registered under `pipx-python`.
- **Exports**: unchanged public surface; one new mapping entry.

### Module: sysup.default_config (default.yaml)
- **Maps to capability**: Wire the capability before the uv upgrade
- **Responsibility**: the new `uv-tool-python` command entry at `order: 35`, `when: { os: darwin, check: uv }`, `use: uv-tool-python`, with a comment stating it pins freestanding uv tools onto the global python minor before `uv tool upgrade --all` re-resolves them.
- **Exports**: none (data).

### Module: docs and changelog
- **Maps to capability**: user-facing description
- **Responsibility**: a short note on the sysup page that freestanding uv tools are pinned to the global python minor before upgrade, mirroring the pipx-tool behaviour. `CHANGELOG.md` under `[Unreleased] / ### Added`: `**sysup**: freestanding uv tools (`uv tool install`) are pinned to the global mise python minor before `uv tool upgrade --all`, so a newly landed CPython minor without compiled wheels (e.g. onnxruntime on cp315) can no longer make the upgrade unsatisfiable; a tool that fails to build on the new minor is reverted to its prior interpreter`.
- **Exports**: none.

### Module: tests
- **Maps to capability**: all
- **Responsibility**: `tests/tools/sysup/test_uv_tool_python.py` mirrors `test_pipx_python.py`'s fake-`subprocess.run` idiom: patch `shutil.which` to resolve `uv`/`mise`, patch `subprocess.run` to answer `uv tool dir`, `mise current python`, `uv python install`, and `uv tool install ...`, and build a fake tools dir under `tmp_path` with per-tool `uv-receipt.toml` files. Assertions key on the reinstall argv (`--python <target> --force <tool>`), the receipt-derived old minor, the revert argv on failure, and the skip/noop messages. `test_default_config.py` asserts the entry exists with the right order/guard/use; `test_invariants.py` globs `capabilities/*.py`, so the new module is covered with no list edit.
- **Exports**: none
- New symbols: `test_pins_unpinned_tool_to_global_minor_and_reinstalls`, `test_moves_stale_pin_to_global_minor`, `test_leaves_current_pin_untouched`, `test_reverts_to_prior_interpreter_when_tool_fails_on_new_minor`, `test_no_tools_is_a_noop`, `test_no_global_python_skips`, `test_missing_uv_or_mise_skips`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.
- **sysup.capabilities.uv_tool_python**: self-contained; uses `StepResult`, stdlib `tomllib`/`subprocess`/`shutil`, same imports as `pipx_python`.

### Integration Layer (Phase 1)
- **sysup.capabilities registry + default.yaml**: Depends on [sysup.capabilities.uv_tool_python].
- **docs and changelog**: Depends on [the wired entry].

## Implementation Phases

### Phase 0: Foundation
**Goal**: the capability exists and is proven by its own tests, independent of wiring.

**Tasks**:
- [ ] Create `src/tools/sysup/capabilities/uv_tool_python.py` with `UvToolPython` modelled on `PipxPython`: `inputs` property, `run(**kwargs)` yielding `StepResult`s, helpers `_tool_dir(uv)`, `_pinned_minor(receipt_path)`, `_global_minor(mise)` (run from `Path.home()`, minor via `^(\d+\.\d+)`). Discovery reads each `<tool>/uv-receipt.toml` with `tomllib`. Reinstall uses `uv tool install --python <target> --force <tool>`; revert uses the prior `--python <old>` or no `--python` when the tool was unpinned (no deps) — Acceptance: `uv run pytest tests/tools/sysup/test_uv_tool_python.py -q` passes all seven named tests; the fake `subprocess.run` never shells out; `test_reverts_...` asserts two `uv tool install` calls for the failing tool (target then revert) and a `kept on python <old>` / `kept unpinned` message.
- [ ] Register `UvToolPython` under the `use:` name `uv-tool-python` in `src/tools/sysup/capabilities/__init__.py`, mirroring the `pipx-python` registration (depends on: previous) — Acceptance: `uv run python -c "from sysup.capabilities import ...; assert 'uv-tool-python' in <registry>"` resolves the class (exact import quoted in the task log after reading `__init__.py`).

**Exit Criteria**: `uv run pytest tests/tools/sysup/test_uv_tool_python.py tests/tools/sysup/test_invariants.py -q` passes (the invariants test auto-globs the new `uv_tool_python.py`).

### Phase 1: Integration
**Goal**: the capability runs in a real sysup plan ahead of the uv upgrade; docs describe it.

**Tasks**:
- [ ] Add the `uv-tool-python` entry to `src/tools/sysup/default.yaml` at `order: 35`, `when: { os: darwin, check: uv }`, `use: uv-tool-python`, with the ordering comment; add the assertion to `tests/tools/sysup/test_default_config.py` (entry present, order between the `uv` entry's lookup and `uv tool upgrade`, guard `os: darwin` + `check: uv`) (depends on: Phase 0). Premise re-checked at execution: the `uv` entry is still `order: 40` with steps `[uv, python, upgrade]` and `[uv, tool, upgrade, --all]`; if the uv step shape changed, stop and report. Acceptance: `uv run pytest tests/tools/sysup/test_default_config.py -q` passes.
- [ ] Update `docs/source/tools/sysup.rst` and `CHANGELOG.md` as specified in the docs module (depends on: previous) — Acceptance: `rg -c "uv tool" docs/source/tools/sysup.rst` prints at least 1; `rg -c "freestanding uv tool\|uv-tool-python\|cp315" CHANGELOG.md` prints at least 1; `uv run sphinx-build -b html docs/source docs/build/html -q` exits 0.

**Exit Criteria**: `uv run pytest -m sysup -q` green; `uv run mypy src/tools/sysup` clean; `uv run ruff check src/tools/sysup tests/tools/sysup/test_uv_tool_python.py` clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: one unpinned tool (receipt has no `python` key), global minor 3.14 -> Expected: `uv python install 3.14` once, `uv tool install --python 3.14 --force <tool>`, one `(python unpinned -> 3.14)` success result.
- **Happy path**: a tool pinned to 3.13, global 3.14 -> Expected: moved, `(python 3.13 -> 3.14)`.
- **Edge case**: a tool already pinned to 3.14, global 3.14 -> Expected: no reinstall call for it; the run yields `all uv tools on python 3.14` when it is the only tool.
- **Edge case**: no tools under the uv tools dir -> Expected: one `no uv tools installed` result, no install calls.
- **Error case**: a tool fails to build on 3.14 -> Expected: a second `uv tool install` reverting it to its prior interpreter (or unpinned), a `success=False` result with `kept on python <old>` / `kept unpinned` and the stderr; other tools still processed.
- **Error case**: `mise current python` empty -> Expected: `success=False`, `no global mise python version, skipping`, no install calls, no filesystem change.
- **Error case**: `uv` or `mise` not on PATH -> Expected: a single skip result, nothing run.

## Risks

- **A tool genuinely needs the newest minor** and has no wheel on the global minor either: the revert path keeps it on its prior interpreter and reports failure (amber-visible via the attention layer); it is not silently downgraded past a working state. Accepted — the operator sees the failed step and can pin that one tool by hand.
- **`uv tool dir` output or receipt schema changes across uv versions**: mitigated by the `$XDG_DATA_HOME`/`~/.local/share/uv/tools` fallback for the dir and by treating a missing `[tool].python` key as unpinned; a receipt that fails to parse is treated as unpinned (so the tool is re-pinned, the safe direction) rather than crashing the run.
- **Ordering vs `uv python upgrade`**: the pin runs at `order: 35`, before both `uv python upgrade` and `uv tool upgrade --all` (`order: 40`). `uv python upgrade` only bumps patch levels of installed minors, so it cannot introduce the newer minor that caused the drift; the pin targets the mise global minor regardless. Mitigated by the `test_default_config` ordering assertion.
- **Divergence from `pipx-python`**: two capabilities now enforce "global python minor" with near-identical logic. Accepted — they act on different tool systems (mise config pins vs uv receipts) and share no mutable state; factoring a common helper is out of scope here and would couple two independently-evolving capabilities.

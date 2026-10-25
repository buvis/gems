---
prd: docs/dev/project-management/prds/wip/00105-sysup-uv-tool-python-pin-v1.md
review: 1
date: 2026-10-25
head_sha: b5d1c173e3565c72b49de9823b49ca5bddca71a0
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
dispatch_rows:
  bob: e332ab9d
---

# Review: 00105-sysup-uv-tool-python-pin-v1

Diff range: `db6b1b434a88c84ce06d25e5773d0225d23de56b..b5d1c173e3565c72b49de9823b49ca5bddca71a0`

codex_rung_guard: not fired
autocodex_alice_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00105-c1-alice-anthropic.txt.receipt.json
autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00105-c1-blake-anthropic.txt.receipt.json
autocodex_bob_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00105-c1-bob-anthropic.txt.receipt.json
provider_review_guard: satisfied

The actual-model provider guard supersedes the legacy rung guard. Eve did not run. All three external Anthropic Opus/xhigh reviewers served claude-opus-5-5 in fresh independent sessions. Receipts retain their distinct session IDs and immutable raw evidence.

## Review Summary

Reviewed all 3 completed tasks. Full suite passed. Optional engram pack unavailable (embedding endpoint refused). Fail-first replay was explicitly skipped because the sandbox denied creating .git/worktrees/wt; no tautological test shapes were found. Carl was not dispatched: no frontend change, host-required roster is Alice/Blake/Bob.

Consolidation is model-side: the script incorrectly merged distinct findings from the same file (including helper naming, allowlist evolution, and customized pin checks). The table below separates those concerns and retains every raw finding.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Found By |
|-----|-----------|----------|-------|------|----------|
| R1 | [2/3] | 🟠 | `engram` gets skipped with `success=False` on every run and stays unpinned. The PRD names it as one of two motivating tools with compiled deps. Its real receipt is an editable install (`{name="engram", editable="/Users/bob/git/src/github.com/buvis/engram"}`), and the requirement allowlist (`name`, `extras`, `specifier`) rejects it. A failed step is red, so `exit_code` returns 1 and `sysup` exits 1 on every run on this host. The original batch failure in `uv tool upgrade --all` stays possible through `engram`. The skip itself is the right call: the PRD's `uv tool install --python X --force <name>` would swap the local editable checkout for a PyPI package. The real gap is the reinstall mechanism. `uv tool upgrade --python <target> <tool>` exists in the host uv and keeps the receipt's requirements; it is the likely fix | src/tools/sysup/capabilities/uv_tool_python.py:64 | BLAKE, ALICE |
| R2 | [2/3] | ⚪ | The migration paragraph now lists `uv-tool-python` among the steps the removed `sysup mac` ran. That is false: the old command never pinned uv tools, and the `pipx-python` precedent left it out of this list. The edited line also runs past the paragraph's wrap width. Revert this hunk | docs/source/tools/sysup.rst:348 | ALICE, BOB |
| R3 | [2/3] | ⚪ | `_install_error` runs a subprocess but has a noun name. Rename it with a verb, e.g. `_run_install`. It is not one of the names the contract fixes | src/tools/sysup/capabilities/uv_tool_python.py:94 | ALICE, BOB |
| R4 | [2/3] | 🟡 | This departs from the spec's error contract. The Risks section says "a receipt that fails to parse is treated as unpinned (so the tool is re-pinned)". The code instead skips any receipt it cannot parse, plus any receipt with a missing table, a version specifier, extras, constraints, overrides, excludes, non-empty options, a foreign entrypoint source, an unknown key or a non-numeric selector. Each one yields a red result. The changelog and docs describe this, but the PRD does not | src/tools/sysup/capabilities/uv_tool_python.py:42 | BLAKE, BOB |
| R5 | [1/3] | 🟡 | Simplification: the `allowed` set repeats the four key names that `dependency_keys` lists again at line 75. Define `dependency_keys` first and build `allowed = {"requirements", "python", "options", "entrypoints", *dependency_keys}`, so the two lists cannot drift apart | src/tools/sysup/capabilities/uv_tool_python.py:48 | ALICE |
| R6 | [1/3] | ⚪ | When the rollback fails, the message reads `reinstall on python <old> also failed: <rollback stderr>: <initial stderr>`. That is two unlabeled diagnostics joined by colons, in reverse order. Label them, e.g. `f"{state} ({recovery}); install on python {target} failed: {error}"` | src/tools/sysup/capabilities/uv_tool_python.py:172 | ALICE |
| R7 | [1/3] | ⚪ | Pre-existing gap, out of scope: the sibling `pipx-python` capability is missing from the built-in capabilities table, which now lists `uv-tool-python` | docs/source/tools/sysup.rst:99 | ALICE |
| R8 | [1/3] | 🟡 | The receipt check is an allowlist, so a future uv release that adds any receipt key (top level, or inside `options`) will make every tool red and unpinned. The capability would turn off loudly after a routine `uv` upgrade | src/tools/sysup/capabilities/uv_tool_python.py:48 | BLAKE |
| R9 | [1/3] | 🟡 | PRD gap: rolling back an unpinned tool runs `uv tool install --force <tool>` with no `--python`. That re-resolves against uv's default interpreter, which may be the same new minor that just failed. So "kept unpinned" does not restore the prior interpreter. That interpreter is still on disk in `<tool>/pyvenv.cfg`. The code matches the spec here, and the docs admit the limit | src/tools/sysup/capabilities/uv_tool_python.py:165 | BLAKE |
| R10 | [1/3] | ⚪ | The code adds an output message the spec does not have: `all uv tools pinned to python X or newer` when a pin is above the target. The spec defines only `all uv tools on python <target>` | src/tools/sysup/capabilities/uv_tool_python.py:149 | BLAKE |
| R11 | [1/3] | ⚪ | The CHANGELOG entry does not use the wording the PRD gives. It leaves out the onnxruntime/cp315 rationale and the "can no longer make the upgrade unsatisfiable" claim. Given the skips, that omission is accurate | CHANGELOG.md:12 | BLAKE |
| R12 | [1/3] | ⚪ | PRD defect: the acceptance commands `rg -c "uv-tool-python\&#124;freestanding uv tool"` use `\&#124;`, which rg treats as a literal `&#124;`. The literal command prints nothing. The corrected `rg -c "uv-tool-python&#124;freestanding uv tool&#124;cp315" CHANGELOG.md` prints 1 | N/A | BLAKE |
| R13 | [1/3] | ⚪ | PRD wording conflicts with itself. The success metric says the entry sits "between the `uv` entry and `mise`'s downstream steps", but the decided design is `order: 35`, before `uv`. The guard text also says "ok-framed skip … not a failure", then re-decides it as `success=False`. The code follows the decided versions | N/A | BLAKE |
| R14 | [1/3] | 🟡 | A customized receipt that is already pinned to the global minor or newer still yields `success=False` on every run. `_pinned_minor` raises on customization before it reads `python`. On this Mac the editable `engram` install would go red forever, and pinning it by hand never clears it. | src/tools/sysup/capabilities/uv_tool_python.py:42 | BOB |
| R15 | [1/3] | ⚪ | `_pinned_minor` and `UvToolPython.run` sit at exactly 50 lines. Commit 5026a1e0 got them there by squeezing lines (`skipped = newer = False`, a dropped blank line) instead of splitting either function. | src/tools/sysup/capabilities/uv_tool_python.py:109 | BOB |
| R16 | [1/3] | ⚪ | The unsafe-receipt test checks only a non-empty message ending in `, skipping`. One generic message for every case would pass. The design says each failure kind (malformed receipt, wrong package name, customization, bad Python version) needs a message the user can tell apart. | tests/tools/sysup/test_uv_tool_python.py:269 | BOB |
| R17 | [1/3] | ⚪ | No test covers `subprocess.run` raising OSError when it tries to start `mise current python` or `uv tool dir`. | tests/tools/sysup/test_uv_tool_python.py:365 | BOB |
| R18 | [1/3] | 🟡 | Every test uses a hand-made receipt. None matches what uv 0.13.5 actually writes (entrypoints with `install-path`, `[tool.options]`). If real receipts carry extra keys, every tool gets skipped as customized and the feature does nothing. | src/tools/sysup/capabilities/uv_tool_python.py:58 | BOB |
| R19 | [1/3] | 🟡 | Full autocodex session logs and session-metadata files are committed. They include `creator_user_id`, `creator_account_id` and your private instruction text, and this repo may be public. | docs/dev/project-management/autopilot/autocodex-sessions/b947d712b2d14e8bbbfd958b3e74d040.jsonl | BOB |
| R20 | [1/3] | ⚪ | The feat commits 0bbe5e97 and a177d948 went in without CHANGELOG.md. The entry came later in the docs commit e47252fa, which breaks the same-commit changelog rule. | CHANGELOG.md:12 | BOB |
| R21 | [1/3] | ⚪ | The full suite needed isolated `XDG_STATE_HOME` and `BUVIS_CONFIG_DIR` values to pass. The klyreon lock tests and the postup collect test touch your real home state and config. Those tests predate this PRD. | N/A | BOB |

## Decision gate

R1 is deferred as a requirements ambiguity under the explicitly reviewed safe plain-install contract. This leaves editable engram exposed to interpreter drift, visible as a failed step. No bare-name reinstall of editable installs is authorized. R2 and R3 enter the consensus tail sweep. R4 is discarded as the reviewed safety refinement. All other Medium/Low rows are single-voice discards under the mandatory Phase 5 rule; raw findings remain below. Account/user IDs are identifiers, not authentication secrets; raw provenance retention is explicitly required by the host contract. No exposed credential was reported. No history rewrite is proposed.

Bob VERIFY items were not queued: installation commands mutate state and multiple chained commands are not eligible project verification checks. Alice and Blake already read real host receipts: mempalace 3.14 and huggingface-hub unpinned parsed successfully; editable engram was visibly rejected. Existing suite isolation and pipx documentation gaps remain durably recorded in this report and the ledger.

## Alice

Provider: Anthropic; served model claude-opus-5-5; effort xhigh.

### Anthropic

[ALICE] 🟡 engram is one of the three host tools the PRD names. It is an editable install (`requirements = [{ name = "engram", editable = "..." }]`), and I confirmed `_pinned_minor` rejects that real receipt with the generic `unsupported requirement customization`. So on this host every sysup run reports a failed `uv-tool-python` step, and engram stays exposed to the cp315 drift the PRD exists to fix. Two fixes: name the rejected key in the message (e.g. `unsupported requirement customization: editable`), and record editable-install support as a deferred backlog item. Right now no PRD or deferral tracks it | File: src/tools/sysup/capabilities/uv_tool_python.py:70 | Task: 1
[ALICE] 🟡 Simplification: the `allowed` set repeats the four key names that `dependency_keys` lists again at line 75. Define `dependency_keys` first and build `allowed = {"requirements", "python", "options", "entrypoints", *dependency_keys}`, so the two lists cannot drift apart | File: src/tools/sysup/capabilities/uv_tool_python.py:48 | Task: 1
[ALICE] ⚪ The migration paragraph now lists `uv-tool-python` among the steps the removed `sysup mac` ran. That is false: the old command never pinned uv tools, and the `pipx-python` precedent left it out of this list. The edited line also runs past the paragraph's wrap width. Revert this hunk | File: docs/source/tools/sysup.rst:348 | Task: 3
[ALICE] ⚪ `_install_error` runs a subprocess but has a noun name. Rename it with a verb, e.g. `_run_install`. It is not one of the names the contract fixes | File: src/tools/sysup/capabilities/uv_tool_python.py:94 | Task: 1
[ALICE] ⚪ When the rollback fails, the message reads `reinstall on python <old> also failed: <rollback stderr>: <initial stderr>`. That is two unlabeled diagnostics joined by colons, in reverse order. Label them, e.g. `f"{state} ({recovery}); install on python {target} failed: {error}"` | File: src/tools/sysup/capabilities/uv_tool_python.py:172 | Task: 1
[ALICE] ⚪ Pre-existing gap, out of scope: the sibling `pipx-python` capability is missing from the built-in capabilities table, which now lists `uv-tool-python` | File: docs/source/tools/sysup.rst:99 | Task: general

Checks I ran:
- The three test files (`test_uv_tool_python.py`, `test_default_config.py`, `test_invariants.py`): 117 passed.
- `ruff check src/tools/sysup` plus both test files: clean.
- `mypy src/tools/sysup`: clean.
- `_pinned_minor` against the three real host receipts: mempalace returned `3.14`, huggingface-hub returned `None` (unpinned, so it gets moved), engram raised `ValueError: unsupported requirement customization`.

`run` and `_pinned_minor` are both exactly 50 lines. The autopilot style checker only flags functions over 50, so R12 passes.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Provider: Anthropic; served model claude-opus-5-5; effort xhigh.

### Anthropic

I left the temporary docs build in place. The removal hook blocked `rm` twice, and the folder sits under `/tmp`, outside the repo.

## Blind audit: PRD 00105 `uv-tool-python`

**What I checked:** `ruff` and `mypy` are clean. The narrow tests pass (117 passed across `test_uv_tool_python.py`, `test_default_config.py` and `test_invariants.py`). `sphinx-build` exits 0. All 7 tests the PRD names exist. The capability is registered and wired at `order: 35`. I also ran `_pinned_minor` against this host's real receipts: `engram` raised `ValueError: unsupported requirement customization`, `huggingface-hub` came back unpinned, and `mempalace` came back as 3.14.

[BLAKE] 🟠 `engram` gets skipped with `success=False` on every run and stays unpinned. The PRD names it as one of two motivating tools with compiled deps. Its real receipt is an editable install (`{name="engram", editable="/Users/bob/git/src/github.com/buvis/engram"}`), and the requirement allowlist (`name`, `extras`, `specifier`) rejects it. A failed step is red, so `exit_code` returns 1 and `sysup` exits 1 on every run on this host. The original batch failure in `uv tool upgrade --all` stays possible through `engram`. The skip itself is the right call: the PRD's `uv tool install --python X --force <name>` would swap the local editable checkout for a PyPI package. The real gap is the reinstall mechanism. `uv tool upgrade --python <target> <tool>` exists in the host uv and keeps the receipt's requirements; it is the likely fix | File: src/tools/sysup/capabilities/uv_tool_python.py:64 | Task: general

[BLAKE] 🟡 This departs from the spec's error contract. The Risks section says "a receipt that fails to parse is treated as unpinned (so the tool is re-pinned)". The code instead skips any receipt it cannot parse, plus any receipt with a missing table, a version specifier, extras, constraints, overrides, excludes, non-empty options, a foreign entrypoint source, an unknown key or a non-numeric selector. Each one yields a red result. The changelog and docs describe this, but the PRD does not | File: src/tools/sysup/capabilities/uv_tool_python.py:42 | Task: 1

[BLAKE] 🟡 The receipt check is an allowlist, so a future uv release that adds any receipt key (top level, or inside `options`) will make every tool red and unpinned. The capability would turn off loudly after a routine `uv` upgrade | File: src/tools/sysup/capabilities/uv_tool_python.py:48 | Task: 1

[BLAKE] 🟡 PRD gap: rolling back an unpinned tool runs `uv tool install --force <tool>` with no `--python`. That re-resolves against uv's default interpreter, which may be the same new minor that just failed. So "kept unpinned" does not restore the prior interpreter. That interpreter is still on disk in `<tool>/pyvenv.cfg`. The code matches the spec here, and the docs admit the limit | File: src/tools/sysup/capabilities/uv_tool_python.py:165 | Task: 1

[BLAKE] ⚪ The code adds an output message the spec does not have: `all uv tools pinned to python X or newer` when a pin is above the target. The spec defines only `all uv tools on python <target>` | File: src/tools/sysup/capabilities/uv_tool_python.py:149 | Task: 1

[BLAKE] ⚪ The CHANGELOG entry does not use the wording the PRD gives. It leaves out the onnxruntime/cp315 rationale and the "can no longer make the upgrade unsatisfiable" claim. Given the skips, that omission is accurate | File: CHANGELOG.md:12 | Task: 4

[BLAKE] ⚪ PRD defect: the acceptance commands `rg -c "uv-tool-python\|freestanding uv tool"` use `\|`, which rg treats as a literal `|`. The literal command prints nothing. The corrected `rg -c "uv-tool-python|freestanding uv tool|cp315" CHANGELOG.md` prints 1 | File: N/A | Task: 4

[BLAKE] ⚪ PRD wording conflicts with itself. The success metric says the entry sits "between the `uv` entry and `mise`'s downstream steps", but the decided design is `order: 35`, before `uv`. The guard text also says "ok-framed skip … not a failure", then re-decides it as `success=False`. The code follows the decided versions | File: N/A | Task: general

B1: fail
B2: fail
B3: pass
B4: pass
B5: fail
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Provider: Anthropic; served model claude-opus-5-5; effort xhigh.

### Anthropic

Review of PRD 00105 (`uv-tool-python`): no Critical or High issues. There are 2 Medium findings with a fix and 2 Medium items that need a named check. Most of the code is correct. A newer pin is left alone, a failed rollback is reported in full, and a broken receipt for one tool does not stop the others. All argv calls are made without a shell. All 12 rubric rules pass.

The first Medium finding matters most on your own Mac. The receipt safety checks run before the pin comparison. Your editable `engram` install will therefore show a red failed step on every `sysup` run, even after you pin it to the current minor by hand. Nothing you do can clear it short of reinstalling `engram` as a plain package.

[BOB] 🟡 A customized receipt that is already pinned to the global minor or newer still yields `success=False` on every run. `_pinned_minor` raises on customization before it reads `python`. On this Mac the editable `engram` install would go red forever, and pinning it by hand never clears it. | File: src/tools/sysup/capabilities/uv_tool_python.py:42 | Task: 1
[BOB] ⚪ `_pinned_minor` and `UvToolPython.run` sit at exactly 50 lines. Commit 5026a1e0 got them there by squeezing lines (`skipped = newer = False`, a dropped blank line) instead of splitting either function. | File: src/tools/sysup/capabilities/uv_tool_python.py:109 | Task: 1
[BOB] ⚪ The unsafe-receipt test checks only a non-empty message ending in `, skipping`. One generic message for every case would pass. The design says each failure kind (malformed receipt, wrong package name, customization, bad Python version) needs a message the user can tell apart. | File: tests/tools/sysup/test_uv_tool_python.py:269 | Task: 1
[BOB] ⚪ The name `_install_error` does not start with a verb, but the function runs an install. | File: src/tools/sysup/capabilities/uv_tool_python.py:94 | Task: 1
[BOB] ⚪ No test covers `subprocess.run` raising OSError when it tries to start `mise current python` or `uv tool dir`. | File: tests/tools/sysup/test_uv_tool_python.py:365 | Task: 1
[BOB] ⚪ The migration sentence now claims `sysup mac` ran `uv-tool-python`. It never did. The test docstring makes the same claim. | File: docs/source/tools/sysup.rst:348 | Task: 3
[BOB] 🟡 Every test uses a hand-made receipt. None matches what uv 0.13.5 actually writes (entrypoints with `install-path`, `[tool.options]`). If real receipts carry extra keys, every tool gets skipped as customized and the feature does nothing. | File: src/tools/sysup/capabilities/uv_tool_python.py:58 | Task: 1
[BOB] 🟡 Full autocodex session logs and session-metadata files are committed. They include `creator_user_id`, `creator_account_id` and your private instruction text, and this repo may be public. | File: docs/dev/project-management/autopilot/autocodex-sessions/b947d712b2d14e8bbbfd958b3e74d040.jsonl | Task: general
[BOB] ⚪ The feat commits 0bbe5e97 and a177d948 went in without CHANGELOG.md. The entry came later in the docs commit e47252fa, which breaks the same-commit changelog rule. | File: CHANGELOG.md:12 | Task: general
[BOB] ⚪ The full suite needed isolated `XDG_STATE_HOME` and `BUVIS_CONFIG_DIR` values to pass. The klyreon lock tests and the postup collect test touch your real home state and config. Those tests predate this PRD. | File: N/A | Task: general
[BOB] ⚪ A malformed receipt is skipped with a failure. The PRD's Risks section said to treat it as unpinned and re-pin it. The design doc changed this on purpose. | File: src/tools/sysup/capabilities/uv_tool_python.py:42 | Task: 1

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

FIX:
- Customized receipt already at the target or newer is reported red forever — src/tools/sysup/capabilities/uv_tool_python.py:42 — Read and compare the `python` value first. Run the package-name and customization checks only for tools that are about to be reinstalled. Move those checks into their own helper, for example `_check_reinstallable(tool, name)`, and call it from `run` before adding a tool to `moves`. Add a test: an editable or `--with` receipt that has `python = "3.14"`, with target 3.14, must produce no failure and no install.
- Both functions sit exactly at the 50-line limit through squeezed lines — src/tools/sysup/capabilities/uv_tool_python.py:109 — The helper from the first fix makes `_pinned_minor` smaller. Pulling the tool listing out of `run` into `_list_tools(root)` restores room, and the squeezed lines can go back to normal form.
- Failure messages are not pinned per kind — tests/tools/sysup/test_uv_tool_python.py:269 — Give each receipt case an expected substring ("missing tool table", "requirements identity", "customization", "entrypoint", "python selector", or the TOML error) and assert it is in `steps[0].message`.
- Function name does not start with a verb — src/tools/sysup/capabilities/uv_tool_python.py:94 — Rename `_install_error` to `_run_install` and update its 3 callers.
- Process-start OSError path is untested — tests/tools/sysup/test_uv_tool_python.py:365 — Add a test where `subprocess.run` raises `OSError("spawn denied")` for `["/bin/mise", "current", "python"]`. Assert exactly one failed `uv tool python` result containing the error text, and no install calls.
- `sysup mac` is credited with a step it never had — docs/source/tools/sysup.rst:348 — Restore the original list and add "plus uv-tool-python before uv" after it. Reword the docstring at tests/tools/sysup/test_default_config.py:17 the same way.
VERIFY:
- Real uv receipts pass the safety check — Run `UV_TOOL_DIR=/tmp/uvt UV_TOOL_BIN_DIR=/tmp/uvb uv tool install --python 3.14 ruff`, then `UV_TOOL_DIR=/tmp/uvt uv run python -c "import os; from pathlib import Path; from sysup.capabilities.uv_tool_python import _pinned_minor; print(_pinned_minor(Path(os.environ['UV_TOOL_DIR'])/'ruff'/'uv-receipt.toml'))"`. Expect `3.14` and no exception. Repeat without `--python`; expect `None`. Then run `_pinned_minor` on each directory under `uv tool dir` on this Mac; `mempalace` should give `3.14`.
- Logs with account IDs may be public — Run `gh repo view buvis/gems --json visibility` and `rg -l creator_account_id docs/dev/project-management`. If the repo is public, check `git check-ignore -v` on `docs/dev/project-management/autopilot/autocodex-sessions/b947d712b2d14e8bbbfd958b3e74d040.jsonl` and on `reports/00105-tess_1-session-metadata.jsonl`. Both should be ignored before anything is pushed.
KNOWN:
- Feat commits shipped without the changelog entry — Those commits are already in history. Fixing them means rewriting history, which needs a force push and your approval. The entry is present at HEAD.
- klyreon and postup tests needed env isolation — That code is outside this diff and older than this PRD. The isolation was a test-environment workaround and no test was weakened. It belongs in a separate fix PRD.
- Malformed receipts are skipped instead of re-pinned — The design doc made this change on purpose and recorded why. Planning rules let the design doc win over the PRD on contract details. A bare reinstall of a receipt it cannot read could throw away the user's install choices.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Verdict: 21 findings
Tests: 5665 passed, 0 failed, 16 skipped (suite run this cycle)

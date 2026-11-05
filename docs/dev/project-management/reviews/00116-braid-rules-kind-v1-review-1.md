---
prd: docs/dev/project-management/prds/wip/00116-braid-rules-kind-v1.md
review: 1
date: 2026-11-05
head_sha: 38aa5eefdf28fd3c87901e5a8466dcd37d8d8af0
codex_thread_id: 01a1adb5-5b3c-7bc2-b900-58da659ce670
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 670fc36c
  carl: 0eda96cc
---

# Review: 00116-braid-rules-kind-v1

Diff range: `147574486c23a69036b89c2f2dd9bcac06665734..38aa5eefdf28fd3c87901e5a8466dcd37d8d8af0`

codex_rung_guard: not fired

## Review Summary

Reviewed: 5 completed tasks
PRDs checked: 00116-braid-rules-kind-v1.md

### Agent Status

- Alice: ✅ Available (native Claude subagent, legacy consensus engine)
- Blake: ✅ Available (native Claude subagent, blind)
- Bob: ✅ Available (codex, inlined prompt)
- Carl: ✅ Available (backend=copilot model=gemini-3.8-flash)

Notes:

- pack: failed (engram pack exit 1: not inside a registered repo; this worktree is not registered with gita). The review ran without the pack.
- Fail-first replay skipped: no `--replay-cmd` passed (the per-file replay needs the Seatbelt env isolation and a Rust build at the base commit). The tautological-shape block ran: 120 test functions, no `[MECH]` lines.
- Consolidation was corrected by hand after `consolidate_findings.py`: it split one finding (keyword-only `emit`, Alice and Bob, rules.py:424 and :425) into two rows, and it folded Blake's render empty-body Low (rules.py:183) into his R5 row after suffix stripping. The table below merges the first pair into R2 (two of four reviewers) and restores the second as R10.
- The test gate parser reported `counts unavailable` for `pytest -q` output. The counts below come from the gate log `docs/dev/tmp/gate-202611051300.log`, line 144.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟠 | Windows regeneration claims a foreign instruction file: sync once, replace the recorded host link with a regular file, then change a rule. `host in regenerated` makes that foreign file owned, so braid backs it up and replaces it instead of reporting UNMANAGED. Capture recorded links that pass `samefile` before generation; permit hard-link replacement only for those hosts. Add this regression test. | src/tools/braid/domain/rules.py:297 | 3 | BOB |
| R2 | [2/4] | 🟡 | `sync_rules` takes `emit` keyword-only (`*, emit`), but the PRD and design give the verbatim contract `sync_rules(settings, inventory, ignored, previous, result, emit)`. A positional call raises TypeError. Drop the `*,` so the exported signature matches. `engine.run` and the tests only pass `emit=` as a keyword, so nothing else changes. | src/tools/braid/domain/rules.py:425 | 3 | ALICE, BOB |
| R3 | [1/4] | 🟡 | The generated-file error paths are untested: `_read_generated` raising `BraidError("cannot read {path}")` on OSError, and `BraidError("cannot write {path}")` when `atomic_write_bytes` fails. Both are in the design contract. No test in tests/tools/braid exercises either message. Add a test that makes the generated file unreadable or the write fail, and asserts the one-line BraidError with nothing silently swallowed. | src/tools/braid/domain/rules.py:222 | 3 | ALICE |
| R4 | [1/4] | 🟡 | Simplification: the private helpers get engine functions through tuple parameters (`engine_sync`, `engine_links`) and bare callables (`backup`, `report`) typed `Callable[..., ...]`. This avoids the engine import cycle but weakens typing and makes the signatures awkward. Replace it with one small `_engine()` function that does the function-local import and returns the helpers (or a lazy import inside each helper). That removes the four plumbing parameters and restores real types. | src/tools/braid/domain/rules.py:226 | 3 | ALICE |
| R5 | [1/4] | 🟡 | After the last rule is removed from every source, the run does not return to the skills-only state. In my probe it wrote header-only `~/.agents/hosts/{codex,copilot,pi,gemini}/AGENTS.md` files (drift=6, generated=4). It also kept a `rules` object with empty maps and four `generated` paths in `.braid-state.json`. The spec says `rules` is "written only when any rule projection exists". If the host roots exist, the instruction links would also point to header-only files. The cause is that `sync_rules` returns None only when `previous is None` and the inventory is empty. Fix: treat an empty inventory as the end of rules, so clean up and drop the state. | src/tools/braid/domain/rules.py:440 | 1 | BLAKE |
| R6 | [1/4] | 🟡 | On Windows under `--check`, a stale hard-linked host instruction path is reported as `UNMANAGED`, not as drift. A path that braid recorded and that no longer points at the generated file (`samefile` fails) is classed as not owned, because `owned` requires `link.is_symlink()` or `host in regenerated`, and `regenerated` is empty outside SYNC. The Risks section says `--check` reports such a link as drift and the next sync relinks it. That holds for the Claude and Kiro file links, which go through `_points_to` and `_sync_links`. It does not hold for the Codex, Copilot, Pi and Gemini instruction links. | src/tools/braid/domain/rules.py:295 | 1 | BLAKE |
| R7 | [1/4] | 🟡 | Host instruction links are built from `Path.home()`, not from `Settings`. `--agents-root` and `--claude-root` overrides still touch the real `~/.codex` and similar directories. The spec names those paths, so this is partly intended, but it is a side effect with no override and no `--no-` flag. | src/tools/braid/domain/rules.py:287 | 1 | BLAKE |
| R8 | [1/4] | ⚪ | braid.rst lists the backup directories for rule links but not the new ones for generated files (`<agents_root>/backups/<stamp>/generated/<host>/`) and host instruction links (`<agents_root>/backups/<stamp>/instructions/<host>/`). Add both lines to the backup list. | docs/source/tools/braid.rst:187 | 5 | ALICE |
| R9 | [1/4] | ⚪ | tests/tools/braid/test_rules.py is 799 lines against the 800-line limit. Any further test lands over it. Move the state-validation cases (`full_state_payload` through `test_layout_of_a_corrupt_rule_state_is_refused`) into their own file. | tests/tools/braid/test_rules.py:487 | 3 | ALICE |
| R10 | [1/4] | ⚪ | `render_host_file` drops empty or whitespace-only rule bodies. The spec says every eligible `RULE.md` body is joined by one blank line. | src/tools/braid/domain/rules.py:183 | 0 | BLAKE |
| R11 | [1/4] | ⚪ | Generated files are written with `atomic_write_bytes`, not the `atomic_write_text` the spec names. The effect is arguably better (exact bytes, no newline translation) but it is a deviation. | src/tools/braid/domain/rules.py:260 | 1 | BLAKE |
| R12 | [1/4] | ⚪ | Beyond the spec, a pre-existing, unrecorded file at a generated path is moved to `backups/<suffix>/generated/<host>` before the write. This is a safe addition but it is scope creep. | src/tools/braid/domain/rules.py:257 | 1 | BLAKE |
| R13 | [1/4] | ⚪ | `make_rule` and `make_host_rule` live in `helpers.py`, not in `conftest.py` as the repo structure lists. | tests/tools/braid/helpers.py:19 | 0 | BLAKE |
| R14 | [1/4] | ⚪ | `RuleState.from_json` does not check state keys against the rule-name regex. A tampered state could make stale-link cleanup unlink a path outside the rules directories. Cleanup only unlinks symlinks (and on Windows hard links) that point at the recorded target, and the skills state has the same exposure. | src/tools/braid/domain/rules.py:90 | 1 | BLAKE |
| R15 | [1/4] | ⚪ | When a host root such as `~/.codex` disappears, `_sync_instruction_links` drops that host's `instructions` record. The link is not removed and the record is lost. | src/tools/braid/domain/rules.py:289 | 1 | BLAKE |

## Alice

- R2 (keyword-only `emit`), R3 (generated read/write error paths untested), R4 (engine helper plumbing), R8 (braid.rst backup dirs), R9 (test_rules.py at 799 lines).
- Verdicts: R1 fail, R2 pass, R3 pass, R4 pass, R6 pass, R7 pass, R8 pass, R9 fail, R10 pass, R11 pass, R12 pass, R13 pass.

## Blake

- R5, R6, R7, R10, R11, R12, R13, R14, R15. Ran `uv run pytest tests/tools/braid` (248 passed) and one sync-then-remove-all-rules probe.
- Verdicts: B1-B19 pass except B2 fail, B6 fail.

## Bob

- R1 (Windows regeneration claims a foreign instruction file), R2 (keyword-only `emit`).
- FIX: 2 items (R1, R2). VERIFY: none. KNOWN: none.

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

- No issues found. Backend copilot, model gemini-3.8-flash. All R1-R13 pass.

Verdict: 15 findings
Tests: 6818 passed, 16 skipped, 1 xfailed (suite run this cycle)

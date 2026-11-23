---
prd: docs/dev/project-management/prds/wip/00161-bim-utc-ids-v1.md
review: 1
date: 2026-11-23
head_sha: 8ae17032443e24a0e46b3debc5485f004d2502f7
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 3c10cb9c
  carl: 8f41be8b
---

# Review: 00161-bim-utc-ids-v1

Diff range: `21adcb929cd2fe897164d1f108c5f1e1186bfcea..8ae17032443e24a0e46b3debc5485f004d2502f7`

codex_rung_guard: not fired

Cycle id: `00161c1-2611231200`. Full review (cycle 1). Context pack: ok. Consensus engine: legacy. Doubt reviewer: codex (Bob), inlined prompt (175959 bytes; the dispatch row's prompt_bytes measured the staged render and understates it). Carl backend: copilot, model gemini-3.8-flash.

Note on the mechanical replay: `--replay-cmd` used this worktree's `.venv/bin/python`, whose editable install resolves `buvis.pybase` to HEAD, not to the base worktree. Its "passes against the pre-change code" lines are therefore not reliable. Verified: base `set_default_id` (21adcb92) keeps the date's own offset digits, so `test_utc_id_ignores_local_offset` (`+02:00 12:00` -> `20240913100000`) cannot pass at base. R19 and R20 carry the two replay rows; the decision gate decides them.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | `get_creation_datetime.assert_called_once_with(f)` is asserted twice in a row. Remove the second line. | tests/lib/zettel/infrastructure/test_zettel_file_parser.py:159 | 2 | ALICE, BOB, CARL |
| R2 | [2/4] | 🟡 | `test_create_never_sleeps` asserts `time.monotonic() - started < 0.3` over 40 `exists()` calls. This is a wall-clock bound that can flake on slow CI filesystems. The assumptions file already records Pat's flake warning. The `time.sleep` patches already catch the real regression, so remove the bound or loosen it. | tests/lib/zettel/application/test_create_zettel_use_case.py:983 | 4 | ALICE, BOB |
| R3 | [1/4] | 🟡 | `prepare` and `execute` repeat the same `next(candidates)` plus `chain([base_path], candidates)` preamble. Both only need the first path for the error message. A small helper, or a `for` loop that remembers the first path, would drop the `chain` import and the duplication. | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:36 | 4 | ALICE |
| R4 | [1/4] | 🟡 | Four new use-case tests pass against the pre-change code: `test_prepare_refuses_existing_slug_path`, `test_warnings_hold_only_the_latest_execute`, `test_destination_outside_vault_is_refused`, and the reworded assertion in `test_body_survives_preparation_when_template_omits_title_metadata`. The PRD does not name them. They guard unchanged behavior and do not pin the UTC or suffix change. Drop them or note them as intentional out-of-scope guards. | tests/lib/zettel/application/test_create_zettel_use_case.py:740 | 4 | ALICE, mech-check |
| R5 | [1/4] | 🟡 | The test file is 798 lines against an 800-line limit, and the added out-of-scope tests used up the headroom. The next change will break the limit. Remove the extra guard tests or split the collision tests into their own file. | tests/lib/zettel/application/test_create_zettel_use_case.py:798 | 4 | ALICE |
| R6 | [1/4] | 🟡 | The spec's edge case "naive date `2026-11-17 08:37:39` gives id `20261117083739` in Python and in Rust" has no Rust-side or parity test. The parity test only covers offset-aware dates. The Rust naive-as-UTC path in `types.rs` is unchanged and correct, and the Python test `test_naive_date_keeps_its_digits` exists, but the Rust/Python identity for naive dates is not pinned | tests/lib/zettel/parity/test_rust_python_parity.py:126 | 3 | BLAKE |
| R7 | [1/4] | 🟡 | The suffix comparison is lexical, so `202401151430００.md` becomes second 59 although its numeric seconds are zero. Use `int(digits[12:]) >= 60`, as specified, and add a regression test for Unicode digits below 60. | src/lib/buvis/pybase/zettel/infrastructure/persistence/file_parsers/zettel_file_parser.py:67 | 2 | BOB |
| R8 | [1/4] | 🟡 | The new collision tests do not pin two explicitly required safeguards: a `None` base must avoid the id setter, and an unused escaping suffix symlink must not reject a free base. Add prepare/execute regression cases for both. | tests/lib/zettel/application/test_create_zettel_use_case.py:405 | 4 | BOB |
| R9 | [1/4] | ⚪ | `raise FileExistsError(...) from None` sits in the `for ... else` branch, where no exception is active. The `from None` does nothing and suggests a handler that is not there. Remove it. | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:84 | 4 | ALICE |
| R10 | [1/4] | ⚪ | The design fixed `_build(...) -> tuple[Zettel, list[Path]]`. The code has `_build(...) -> Zettel` plus a lazy `_candidate_paths` generator. Behavior matches the contract, and the assumptions file records the change. A caller or test that relies on the contracted name and signature would break. | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:114 | 4 | ALICE |
| R11 | [1/4] | ⚪ | `set_default_id` uses `date.tzinfo is not None`. A `tzinfo` whose `utcoffset()` returns `None` goes through `astimezone()` and is read as local time. The design allows the stricter `date.utcoffset() is not None`, and the assumptions file records that no test covers this case. | src/lib/buvis/pybase/zettel/domain/entities/zettel/fixers/set_default_id.py:22 | 1 | ALICE |
| R12 | [1/4] | ⚪ | The doc comment on Rust `set_default_date` says "Local time, like the vault's Templater notes". The vault Templater notes now write UTC ids, so a reader may take the comment as a statement about ids. Say that only the date stays local and the id is UTC. | src/rust/src/consistency/defaults.rs:21 | 3 | ALICE |
| R13 | [1/4] | ⚪ | The `docs/dev/project-management/meta/assumptions.md` diff replaces the PRD 00118 assumptions with the PRD 00161 ones. This is pipeline bookkeeping. Check that the 00118 content survives elsewhere. | docs/dev/project-management/meta/assumptions.md:1 | general | ALICE |
| R14 | [1/4] | ⚪ | `TestCollisionBudget` keeps its old class name although it now holds the new suffix tests. The old five test names are gone, so this is cosmetic only | tests/lib/zettel/application/test_create_zettel_use_case.py:402 | 4 | BLAKE |
| R15 | [1/4] | ⚪ | I could not run `cargo test`, so the Rust acceptance criterion is unverified by me. `cargo test --offline` fails with "no matching package named chrono" (no cached crates in the scratch CARGO_HOME). I read the Rust unit tests (`defaults.rs`, `enrichment.rs`) and they match the spec rules. The Python parity tests pass against the built extension, which exercises the same Rust code | src/rust/src/consistency/defaults.rs | 3 | BLAKE |
| R16 | [1/4] | ⚪ | The supplied test gate carries no counts (exit 1, no summary line), so I cannot confirm the full-suite state. The five spec-named Python test files pass when run narrowly: 338 passed. I did not run the full `tests/lib/zettel tests/tools/bim` set or `sphinx-build` | N/A | general | BLAKE |
| R17 | [1/4] | ⚪ | The required documentation-build result is absent from the supplied verification evidence. Check `uv run sphinx-build -b html docs/source docs/build/html` exits successfully for the reviewed revision. | docs/source/tools/bim.rst:249 | 5 | BOB |
| R18 | [1/4] | ⚪ | The full suite has 10 fixture-setup errors from missing git identity; it is not green. These errors concern unchanged dot tests and are tracked in `docs/dev/project-management/autopilot/deferred/202611231043-deferred.json`, so their repair is outside this PRD. | tests/tools/dot/test_pull_divergence_two_hosts.py | general | BOB |
| R19 | [1/4] | 🟡 | 11 touched test(s) pass against the pre-change code: test_utc_id_ignores_local_offset, test_naive_date_keeps_its_digits +5 more | tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py | general | mech-check |
| R20 | [1/4] | 🟡 | 54 touched test(s) pass against the pre-change code: test_invalid_file_name_date_falls_back_to_earliest_file_date +48 more | tests/lib/zettel/infrastructure/test_zettel_file_parser.py | general | mech-check |

## Alice

No blocking issues. Ran `tests/lib/zettel` and `tests/tools/bim`: 2450 passed, 0 skipped; parity + use-case files with `-rs`: 186 passed, no skips. Did not run `cargo test` or sphinx. Findings R1-R5, R9-R13 above.

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

Blind lens. Spec rules for `set_default_id`, `_get_date_from_file`, Rust `set_default_id` / `date_from_filename`, `CACHE_VERSION` 5, the 60-99 candidate loop, docs and CHANGELOG checked compliant. Findings R6, R14-R16 above.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
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

Doubt lens (codex, inlined prompt). FIX: R7, R2, R8, R1. VERIFY: R17 (queued in `00161-bim-utc-ids-v1-checks-1.json`). KNOWN: R18.

R1: fail
R2: pass
R3: pass
R4: pass
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

Backend copilot, model gemini-3.8-flash. Ran zettel/bim tests, `cargo test`, `sphinx-build` and mypy (results not reported in his text beyond the finding). Finding R1 above.

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

Verdict: 20 findings
Tests: 7486 passed, 16 skipped, 1 xfailed, 10 errors (suite run this cycle; the gate's summary parser found no PASS/FAIL line, counts read from docs/dev/tmp/gate-00161c1-2611231200.log; all 10 errors are fixture setup in tests/tools/dot/test_pull_divergence_two_hosts.py, git commit exit 128 because the gate command unset GIT_AUTHOR_*/GIT_COMMITTER_*; untouched by this PRD)

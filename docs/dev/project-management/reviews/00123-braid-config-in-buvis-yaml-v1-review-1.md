---
prd: docs/dev/project-management/prds/wip/00123-braid-config-in-buvis-yaml-v1.md
review: 1
date: 2026-11-10
head_sha: 95a053a2436de495ed5da4f1f59ebaa504a5dc94
codex_thread_id: 01a1c582-b889-7f31-a1a2-7b08a9c6e888
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: e8aeba85
  carl: e58a753d
---

# Review: 00123-braid-config-in-buvis-yaml-v1

Diff range: `b3ef0a5d7ba245f2048b922d58529cac28dfe33e..95a053a2436de495ed5da4f1f59ebaa504a5dc94`

codex_rung_guard: not fired

Engram context pack: failed (repo not gita-registered) — review degraded, not invalid.

## Review Summary

Reviewed: 5 completed tasks
Reviewers that ran: Alice (consensus), Blake (blind), Bob (doubt, codex), Carl (gemini)
No CRITICAL and no HIGH finding. Every consolidated row is single-voice `[1/4]`.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟡 | `test_no_sources_is_refused_without_reading_the_old_sources_d` builds two legacy `sources.d` trees and sets `BUVIS_BRAID_CONFIG_ROOT`, but `resolve_settings` reads neither env nor disk for sources, so none of that setup can influence the result; the name's promise is unenforced scaffolding - drop the setup or move the claim to a CLI-layer test | tests/tools/braid/test_engine.py:337 | 1 | ALICE |
| R2 | [1/4] | 🟡 | `_expand_configured` returns expanded paths that `_deduplicate`/`_resolved` immediately re-expand, so only its absoluteness check is load-bearing; simplify to a validate-only `_reject_relative(key, entries) -> None` and pass `request.configured_sources`/`configured_policies` straight into `_deduplicate` and `candidates` | src/tools/braid/domain/engine.py:560 | 1 | ALICE |
| R3 | [1/4] | 🟡 | A malformed `sources:`/`policies:` value in `buvis-braid.yaml` (e.g. a bare scalar `sources: ~/personal` instead of a list) escapes as an uncaught `ConfigurationError` from the settings resolve inside the Click callback, so the user gets a traceback and exit 1 - while docs/source/tools/braid.rst:227 documents exit 1 as "--check found drift" and the repo convention forbids raw exceptions reaching the user. Reproduced with a CliRunner probe at HEAD. | src/lib/buvis/pybase/configuration/click_integration.py:291 | general | BLAKE |
| R4 | [1/4] | ⚪ | The `.braidignore` source list names `policies` but never states that entries must be absolute or start with `~`, although a relative entry aborts the whole run | docs/source/tools/braid.rst:76 | 4 | ALICE |
| R5 | [1/4] | ⚪ | PRD task 4 and Phase 1 acceptance greps are unsatisfiable as written: the migration note must name `sources.d` and `test_cli_help_does_not_offer_config_root` contains `config_root`; the build followed the PRD Contract text instead, which is the right call - record the PRD self-contradiction rather than "fixing" the code | N/A | general | ALICE |
| R6 | [1/4] | ⚪ | Doc markup/wrap drift: the intro line runs ~95 chars where the file wraps near 72, and `docs/source/tools.rst:37` plus `README.md:96` write buvis-braid.yaml as plain text while neighbouring filenames use literal markup | docs/source/tools/braid.rst:7 | 4 | ALICE |
| R7 | [1/4] | ⚪ | YAML `policies` and `--policy` are each tested alone but never combined, so the configured-then-CLI policy order is unproven at the CLI layer; the sources side has the equivalent combined test at tests/tools/braid/test_cli.py:115 | tests/tools/braid/test_cli.py:137 | 3 | ALICE |
| R8 | [1/4] | ⚪ | The PRD's own acceptance commands cannot pass as written: the rg clause over docs/source still hits docs/source/tools/braid.rst:216, which the Docs feature itself mandates, and the Phase 1 variant over tests/tools/braid hits the PRD-mandated test name test_cli_help_does_not_offer_config_root plus the legacy-path regression tests. The implementation chose the behavior text over the literal rg clause, which is the right call. | docs/source/tools/braid.rst:216 | general | BLAKE |
| R9 | [1/4] | ⚪ | The new fields silently add BUVIS_BRAID_SOURCES and BUVIS_BRAID_POLICIES env overrides (verified working, JSON-list syntax), but the Configuration table lists only the three root env names. Either document them or note deliberately that only roots have env names. | docs/source/tools/braid.rst:203 | general | BLAKE |
| R10 | [1/4] | ⚪ | Migration loses a `~/.config/braid/.braidignore` with no warning: that candidate was removed from the policy list, so the first post-upgrade sync on a machine that had one would start projecting previously-ignored skills into the Claude root. The PRD accepts the no-fallback risk and the changelog names the directory, but braid emits nothing when the directory exists. | src/tools/braid/domain/engine.py:580 | general | BLAKE |
| R11 | [1/4] | ⚪ | Test Strategy's error case "YAML sources: [skills] (relative) -> error names the entry, nothing written" is covered only at resolve_settings level; no CLI-level test asserts exit 2 and an empty ~/.agents for a relative YAML entry, unlike the no-sources case which has both. | tests/tools/braid/test_engine.py:351 | 1 | BLAKE |
| R12 | [1/4] | ⚪ | The required zero-match removal checks conflict with retained migration text and required negative tests. Update the PRD checks to permit historical references and absence assertions. | docs/source/tools/braid.rst:217 | general | BOB |

## Alice

Six findings (2 🟡, 4 ⚪), listed above as R1, R2, R4, R5, R6, R7. All twelve consensus rubric rules pass.

Verification she ran herself: braid suite 265 passed; mypy clean on `src/tools/braid/` and the configuration package; `ruff check` clean; sphinx-build clean. Fail-first replay: restoring the three pre-change sources made all 15 new/changed tests fail, then HEAD restored them green — the tests pin this change. Stale `config_root:` YAML key and stale `BUVIS_BRAID_CONFIG_ROOT` env var are both ignored (both PRD risk notes hold). Task 2's Kiro premise re-checked: enrollment state is written only under `settings.agents_root / ".braid-state.json"`. Largest changed function `cli` at 49 lines; largest changed file `tests/tools/braid/test_rules.py` at 798 lines (the diff shrank it).

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

Five findings (1 🟡, 4 ⚪), listed above as R3, R8, R9, R10, R11. All nineteen blind rubric rules pass.

He located the code from the PRD alone and verified independently: braid suite 265 passed, mypy clean (12 files), sphinx clean, plus three live probes (stale env var ignored, stale YAML key ignored, `BUVIS_BRAID_SOURCES` JSON-list override working). Spec compliance confirmed field by field: `configured_sources`/`configured_policies` replace `config_root`, `read_configured_sources` and its `__all__` entry are gone, `~` expansion and the verbatim relative-entry error are in place, defaults are `()`, `--config-root` is gone, the policy candidate order matches the contract, all seven PRD "New symbols" tests exist, and docs/manifest/README/AGENTS.md/CHANGELOG match the spec text.

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

One ⚪ finding (R12 above): the PRD's own zero-match removal checks conflict with the retained migration text and the required negative tests.

FIX: R12. VERIFY: none. KNOWN: none.

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

`[CARL] ✅ No issues found`. He read the context and diff, ran the braid tests, mypy and sphinx, and searched for every `config_root`/`sources.d`/`config/braid` remnant and for TODO/FIXME/print markers.

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

Verdict: 12 findings
Tests: 7262 passed, 0 failed, 16 skipped (suite run this cycle)

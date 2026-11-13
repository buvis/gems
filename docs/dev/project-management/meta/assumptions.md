# Assumptions ledger: 00137-yaml-auto-update-ignored-v1

## 1: Run the update check after settings resolution so YAML auto_update: false is honoured

- Tess: used `log_level: BOGUS` as the "reliably fails config resolution" trigger for the resolution-failure test, since an unknown top-level key is silently dropped by `GlobalSettings`'s env-merge rather than raising; an invalid `Literal` value for an existing field reliably raises `ConfigurationError` instead.
- Tess: did not assert on the exact object/fields passed to `check_and_update` (e.g. that it carries `auto_update`/`installer`) since the acceptance criteria only specify whether the call happens, not its argument shape.
- Ivan: `GlobalSettings` exposes a boolean `auto_update` field read from env var `BUVIS_AUTO_UPDATE` and YAML key `auto_update`.
- Ivan: `ConfigResolver.resolve(settings_class, config_dir=None, config_path=..., cli_overrides={})` is a safe call shape for the early (pre-wrapper) check, mirroring the wrapper's own defaults.
- Ivan: the update check parses `--config` (and `--config=VALUE`) directly from raw argv to resolve settings before Click's own option parsing runs; `--config-dir` is intentionally not extracted at this early stage since no failing test exercises it.
- Ivan: if settings resolution raises (bad config), the check silently no-ops for that invocation too, consistent with the existing `contextlib.suppress(Exception)` pattern and the acceptance criterion that a config error already reports as today.
- Orchestrator: kept the update check inside the `parse_args` monkeypatch (not moved into the command wrapper after resolution, contrary to a literal reading of the PRD's "move after settings resolution") because three pre-existing tests require the check to still fire before `--help`/`--version` eager-exit, which the wrapper body never reaches for those flags; judged this satisfies the PRD's actual intent (honour resolved YAML/env `auto_update`) rather than its literal code-location wording.
- Orchestrator: per-task review (step 5.7, Pat) could not run - `sonnet-run.sh` failed with "OAuth token revoked" (headless `claude -p` lacks `CLAUDE_CODE_OAUTH_TOKEN` in this session), retried once (same failure class), then recorded `review: failed:runner_unavailable` and proceeded per the per-task review's fail-loud fallback; the mandatory PRD-level review lenses cover what Pat would have.

## 2 (rework cycle 1): [D1] tests/tools/sysup/conftest.py

- Ivan: `runner: CliRunner` annotation style (parameter annotated under `TYPE_CHECKING`) is the convention the contract meant; the contract's snippet showed the parameter unannotated.
- Ivan: the `Verify` section's directory-scoped command (`uv run pytest tests/tools/sysup`) overrides the general "run only the named test files" rule, since the task states it explicitly.
- Orchestrator: `sonnet-run.sh` again failed with "OAuth token revoked" (twice, plus once without `-S`), so Pat was rerouted to the native `autopilot:pat` subagent at sonnet rather than dropped - same persona, same rendered prompt, same reporting contract. Verdict: `CLOSURE | resolved` for the 🔴 finding, then `NO FINDINGS`. Recorded in the attempt as `review_note`; the closed `review` stamp grammar has no value for "clean review on a rerouted lane".

## 3 (rework cycle 1): [D1] src/lib/buvis/pybase/configuration/click_integration.py

- Ivan: ASSUMPTIONS: none.
- Orchestrator: skipped Tess for this task. Tasks 3 and 5 both covered the same behaviours, and the rework design assigns the new tests to task 5's module; dispatching Tess here would have authored a competing module over exactly task 5's listed gaps. The fail-first evidence used instead was the two already-red `tests/tools/dot/test_filter_cli.py::TestFilterIsolation` cases (`AssertionError: uv was executed`), which the design names as the regression test for the lost global env opt-out. Recorded in `autonomous_decisions`.
- Orchestrator: Pat rerouted to the native lane again (same auth failure); 2x `CLOSURE | resolved`, `NO FINDINGS`.

## 4 (rework cycle 1): [D1] docs/source/configuration.rst

- Orchestrator: took the micro lane (one non-CRITICAL finding, one clean file, 1 net line). Pat was skipped per SKILL.md step 5.7's documentation-only rule; the finding was "replace it with the sentence the rework design specifies verbatim", so closure was checked deterministically instead - the verbatim sentence is at `:830` and the `fully resolved settings (CLI > ENV > YAML > defaults)` overclaim is gone from that paragraph. The one remaining occurrence of that phrase (`:191`) describes general option resolution and is accurate, so it was left alone per the surgical-changes rule.

## 5 (rework cycle 1): [D1] tests/lib/pybase/configuration/test_click_integration_auto_update.py

- Ivan: spec case 1 was tested with both plain `GlobalSettings` (failed) and a `FooSettings` (`BUVIS_FOO_`) tool class (passed).
- Ivan: the empty-`--config-dir` case is discriminated with `BUVIS_CONFIG_DIR` pointing at an `auto_update: true` dir and a cwd config of `auto_update: false`, because cwd is always searched by default; a plain cwd file alone cannot tell the two behaviours apart.
- Ivan: the trailing-bare-`--config` case was checked on the `CliRunner` outcome only, ignoring the exit code (Click rejects the bare flag after the check has already run). **Superseded**: Pat raised this as a LOW and the test now asserts `exit_code == 2` explicitly.
- Ivan: the `updater.json` case pre-seeds the file in the isolated `~/.config/buvis` and asserts its bytes and mtime are unchanged, plus that no new file appears under `~/.local/.config/buvis`. **Superseded**: Pat raised that `check_and_update` is mocked so the file assertions cannot fail; the test now asserts `assert_not_called()` as the real suppression signal, with the file assertions kept as a secondary guard.
- Ivan: the malformed-config case uses `--help` so exit 0 is assertable, since a bad config otherwise fails the command's own resolution with exit 1.
- Ivan: the `--` sentinel case uses a throwaway command with a `rest` nargs=-1 positional argument.
- Orchestrator: Ivan reported 2 of 20 cases failing and correctly refused to touch `src/` or soften them. Adjudicated separately. (a) The empty-`--config-dir` failure is a REAL defect in cycle 1's own code, contradicting the rework design's Risks pin ("an empty value is treated as absent, because `Path("")` expands to the cwd inside `loader.py:208`"); fixed in production with `config_dir=config_dir or None`. (b) The plain-`GlobalSettings` failure is the test encoding a rule the contract does not promise: `GlobalSettings` carries the default `BUVIS_` prefix, so `BUVIS_AUTO_UPDATE` *is* its tool-prefixed variable and `_update_enabled`'s first branch is correct; the YAML wins because of the documented `_merge_overrides` hole the design places out of scope. That test was rewritten to pin the actual documented behaviour with a docstring naming the reason, and the tool-prefixed twin (which does run the check) pins the contract's real rule. No assertion was softened to a tautology.

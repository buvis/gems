# Autocodex efficiency observations

Scope: manage PRD `00105-sysup-uv-tool-python-pin-v1.md` and observe autopilot overhead. Batch `202610242315`. Observation started 2026-10-25 Europe/Prague.

## Baseline

The build finished successfully and committed the review handoff at `b5d1c173`. The wrapper then failed because its metrics override lacked the parent's new `launched_prd` parameter. Dotfiles commit `9898d65b` fixes the mismatch; all 109 adapter tests passed. No build replay is needed.

Evidence: `autocodex-sessions/b947d712b2d14e8bbbfd958b3e74d040.jsonl`, `reports/00105-sysup-uv-tool-python-pin-v1-build-evidence.md`, and the preserved initial/isolated suite logs.

The raw coordinator log contains 192 completed shell-command events: 181 report exit 0, nine exit 1, and two exit 2. These are event counts, not unique commands or all delegated-worker activity. Repeated validation after a code change is legitimate and is not counted as waste merely because its argv repeats.

The final turn reports 35,433,390 cumulative input tokens, of which 35,197,056 are cached, plus 51,109 output tokens (including 16,325 reasoning-output tokens). The cached share is 99.33%; the input difference is 236,334. These are reported cumulative usage totals, not the context-window size or a dollar-cost estimate.

## Findings and next-run controls

| Evidence | Observation | Control |
| --- | --- | --- |
| Command events `item_67`, `item_156`; retained auth-failure reports | Claude authentication failed during design review and again during task review. Completion review requires this provider. | Check host authentication before resuming. Preserve the provider guard and terminal failure handling. |
| `item_131`, `item_170` | Two commit attempts failed because the formatting hook modified one file each; each hook examined 1,032 files. | Format changed files before commit. Retain mandatory hooks. Broader hook-scoping changes require separate analysis. |
| `item_140` | Mechanical style checks found 51- and 52-line functions after implementation commit, requiring a repair commit. | Run the existing style check before commit. The tests repeated after this repair were justified. |
| Initial and isolated full-suite logs | Initial run: 5,662 passed, three failed in 129.88s. Host-state/config isolation fixed those three without code changes. The required confirming full run passed 5,665 tests in 111.86s. | Use the documented isolated configuration for required future suite runs; reuse canonical evidence only when gates allow. |
| `item_77` | An inline shell/Python artifact writer expanded Markdown fragments as shell commands. The command reported exit 0 while output contained command-not-found errors. | Write artifacts with edit tools or safe multiline quoting. Verify substantive output, not exit code alone. |
| Wrapper traceback after successful `turn.completed` | Metrics signature drift prevented loop continuation and omitted this session's metrics row. | Adapter regression tests now cover the installed loop and PRD attribution; retain raw usage evidence without fabricating a historical metrics row. |

## Supervision status

At preflight, state remains `review -> review`, all three build tasks are complete, and there is no ready backlog. An advisory-lock probe found no active autocodex loop. Claude auth status inside the macOS sandbox reports `loggedIn: false`; this cannot establish host authentication because Keychain reads are denied there. The preceding build separately recorded an expired OAuth session.

The operator subsequently confirmed that Claude has reached its usage limit. No run was launched. State remains at the saved review handoff. The prepared launch entrypoint under `docs/dev/tmp/autocodex-monitor-20261025/` is disabled; pending warrant request `b62167a40db14129f54fc4f9127fefe8` must not be used to launch. A future run needs fresh preparation after reviewer availability is restored.

No quota reset timestamp is present in the inspected evidence: the two retained failure reports contain authentication errors, not structured quota metadata. Do not infer a reset time from those errors. The reviewer helper already waits for a confirmed structured 429 reset plus five seconds, bounded by its existing deadline; successful login alone does not establish available quota. This preflight must consider both credentials and quota before starting a costly coordinator session.

When execution resumes, observe each fresh session's raw events, phase/cycle transitions, external-review results, retries, and available usage counters. Preserve every required lens and the existing model-provider review guard; no substitute provider has been authorized. Do not increase caps to improve throughput.

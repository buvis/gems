# Implementation model audit — review cycle 2

PRD: `00110-backup-plan-preview-and-output-resolution-v1.md`; cycle: 2; work start: `7f4b462f1275c9306d7cc452cb2024a429f2c371`.

Fingerprint: `3baeaf4a31599a806cbd25f0d3e27604f27d3390f810d61c590957c5b62d3c44`. The installed autocodex driver's `implementation_snapshot(state)` and `implementation_fingerprint(state)` generated the JSON contract without changing state.

The original cycle-1 audit and explanation are preserved byte-for-byte in `00110-backup-plan-preview-and-output-resolution-v1-implementation-models-cycle-1.json` and `00110-backup-plan-preview-and-output-resolution-v1-implementation-models-cycle-1.md`. All 17 original evidence rows remain unchanged. Nine rework contributor sessions add evidence for tasks 6 and 7. Each SHA-256 covers the exact cited line bytes without its newline.

All 12 original worker/session copies were compared byte-for-byte with the source line numbers in the five task-native-sessions manifests. All 12 rework metadata files were matched against the original raw sessions, and their complete-file hashes match `00110-c1-rework-provenance.json`. Raw native `turn_context` records and Claude assistant `message.model` records confirm observed served models and efforts. Planning, prompts, coordinator prose and requested aliases are not model evidence.

| Task | Contributor | Observed model | Effort | Copied evidence | Original source line |
|---|---|---|---|---|---|
| 1 | ivan_1 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_1-metadata.jsonl:2` | 10 |
| 1 | tess_1 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_1-metadata.jsonl:2` | 10 |
| 1 | tess_1 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_1-metadata.jsonl:3` | 63 |
| 2 | ivan_2 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_2-metadata.jsonl:2` | 10 |
| 2 | tess_2 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_2-metadata.jsonl:2` | 10 |
| 2 | tess_2 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_2-metadata.jsonl:3` | 113 |
| 2 | style_2 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/style_2-metadata.jsonl:2` | 10 |
| 2 | style_2_astra | gpt-6-astra | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/style_2_astra-metadata.jsonl:2` | 10 |
| 3 | ivan_3 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_3-metadata.jsonl:2` | 10 |
| 3 | tess_3 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_3-metadata.jsonl:2` | 10 |
| 3 | tess_3 | gpt-6.1-sol | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_3-metadata.jsonl:3` | 131 |
| 3 | ivan_3_astra | gpt-6-astra | high | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_3_astra-metadata.jsonl:2` | 10 |
| 4 | tess_4 | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_4-metadata.jsonl:2` | 10 |
| 4 | tess_4 | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_4-metadata.jsonl:3` | 139 |
| 4 | ivan_4 | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_4-metadata.jsonl:2` | 10 |
| 4 | ivan_4 | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_4-metadata.jsonl:3` | 92 |
| 5 | ivan_5 | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_5-metadata.jsonl:2` | 10 |
| 7 | tess7_contract | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/tess7_contract-metadata.jsonl:2` | 10 |
| 6 | tess6 | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/tess6-metadata.jsonl:2` | 10 |
| 6 | tess6_boundary | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/tess6_boundary-metadata.jsonl:2` | 10 |
| 7 | tess7 | gpt-6.1-sol | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/tess7-metadata.jsonl:2` | 10 |
| 6 | ivan-6-initial | claude-sonnet-5-5 | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/ivan-6-initial-metadata.jsonl:4` | 41 |
| 6 | ivan-6-retry-1 | claude-sonnet-5-5 | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/ivan-6-retry-1-metadata.jsonl:3` | 36 |
| 7 | ivan-7 | claude-sonnet-5-5 | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/ivan-7-metadata.jsonl:4` | 40 |
| 7 | ivan-7-retry-1 | claude-sonnet-5-5 | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/ivan-7-retry-1-metadata.jsonl:3` | 36 |
| 7 | ivan-7-review-fix | claude-sonnet-5-5 | medium | `docs/dev/project-management/autopilot/reports/00110-c1-rework-evidence/ivan-7-review-fix-metadata.jsonl:6` | 48 |

Original task correlation: tasks 1–3 used logical Opus mapped to OpenAI `gpt-6.1-sol`/high. Task 2 style/lint repair and task 3 type/path repair contributed `gpt-6-astra`/high and remain separate attempts. Tasks 4–5 used native logical Sonnet mapped to `gpt-6.1-sol`/medium. Test writers, initial implementation, contributing style extraction and retained repair attempts are all included. Original source paths/session IDs are in `task-1-native-sessions.json` through `task-5-native-sessions.json` and the archived Markdown audit. Original test/implementation commits and gate triggers are recorded in the build report.

Rework task 6 includes Tess initial and timestamp-boundary tests (`tess6`, `tess6_boundary`), Claude initial implementation (`ivan-6-initial`, session `bd4c4e3c-4ba7-44f6-ba73-8849e1c5c060`), and its same-tier repair (`ivan-6-retry-1`, session `3f43a765-6b5e-4556-8892-b7f45f51aaf3`). Task 7 includes Tess regressions and legacy-contract correction (`tess7`, `tess7_contract`), Claude initial implementation (`ivan-7`, session `58d8bca9-27a9-4f53-925f-3f6e1c2dc17a`), same-tier hook repair (`ivan-7-retry-1`, session `71044b55-e465-4536-98cd-12f638827173`), and final closure repair (`ivan-7-review-fix`, session `8f62c953-956d-4a72-b18a-6154a998ac5e`). Claude evidence cites actual Edit requests carrying observed model metadata. The rework provenance manifest maps every copied file to its exact raw source; the work report and dispatch ledger correlate bounded retries and commits `38dfe8ad`, `f56aaf72`, `ee0bc71f`, `9b20c713`, `7eeb8cae`, `9b266a1d`, `fc8e4069`.

The current state correctly records original OpenAI attempts and Anthropic rework attempts, including task 7 attempt 2; no `actual_model` or `actual_provider` correction was warranted. Retry sessions within the same recorded attempt remain separately evidenced here. Test writers are implementation contributors for routing even though attempt ownership records the production implementor. Raw served-model records contain no additional model switch beyond the original Sol-to-Astra escalations.

Excluded contributors: the task 6 one-shot Claude style fixer made no edits; Pat sessions were read-only per-task reviews. Original coordinator/planning models, guardian approvals, restored Devon adversarial code, no-op cleanup and read-only Pat reviews remain excluded. Unsupported Qwen implementation routing fell back before dispatch; task 5 unhealthy Codex-hook preflight prevented external implementation; no Gemini contribution occurred. None of these exclusions relabels retained implementation.

Required cycle-2 review providers are **Anthropic and OpenAI**, with each provider independently running the complete Alice, Blake and Bob roster over the whole change. The driver validates current fingerprint, all 26 evidence hashes, exact model strings and complete task coverage. This audit does not claim any cycle-2 review result, receipt, convergence or phase transition.

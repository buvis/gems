# Implementation model audit

PRD: 00110-backup-plan-preview-and-output-resolution-v1.md; cycle1; work_start_sha 7f4b462f1275c9306d7cc452cb2024a429f2c371.

The JSON fingerprint/snapshot is computed with the installed autocodex driver. Each evidence line is an exact copied native session turn_context line, SHA-256 over its bytes without newline. The sibling task-native-sessions manifests map copied lines to original raw session files/source-line numbers. session_meta independently identifies parent thread, native agent path, session id and OpenAI provider. Only the current parent thread is included. No prompt examples or arbitrary model-name grep were used.

| Task | Worker | Session | Observed model | Effort | Exact copied evidence |
|---|---|---|---|---|---|
| 1 | /root/ivan_1 | 01a189fe-61cf-7002-abba-83cccffe46d1 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_1-metadata.jsonl:2 |
| 1 | /root/tess_1 | 01a189f8-cb77-73f0-9cce-0dedcec94138 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_1-metadata.jsonl:2 |
| 1 | /root/tess_1 | 01a189f8-cb77-73f0-9cce-0dedcec94138 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_1-metadata.jsonl:3 |
| 2 | /root/ivan_2 | 01a18a0b-cfe0-7372-8c58-2797c1922dae | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_2-metadata.jsonl:2 |
| 2 | /root/tess_2 | 01a18a01-703e-7ea2-bafa-e1e6d9488164 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_2-metadata.jsonl:2 |
| 2 | /root/tess_2 | 01a18a01-703e-7ea2-bafa-e1e6d9488164 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_2-metadata.jsonl:3 |
| 2 | /root/style_2 | 01a18a10-300f-7921-9353-b77e789fcce7 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/style_2-metadata.jsonl:2 |
| 2 | /root/style_2_astra | 01a18a13-50ca-7843-93d9-bca5e4f0bb9a | gpt-6-astra | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/style_2_astra-metadata.jsonl:2 |
| 3 | /root/ivan_3 | 01a18a24-ba49-70a0-b5da-84af879b226f | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_3-metadata.jsonl:2 |
| 3 | /root/tess_3 | 01a18a17-1393-7161-ad6a-0e70cf59c1e3 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_3-metadata.jsonl:2 |
| 3 | /root/tess_3 | 01a18a17-1393-7161-ad6a-0e70cf59c1e3 | gpt-6.1-sol | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_3-metadata.jsonl:3 |
| 3 | /root/ivan_3_astra | 01a18a29-8725-7403-b1be-0f6888c83b1b | gpt-6-astra | high | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_3_astra-metadata.jsonl:2 |
| 4 | /root/tess_4 | 01a18a34-fc84-7d50-85dd-c6ce929c7e26 | gpt-6.1-sol | medium | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_4-metadata.jsonl:2 |
| 4 | /root/tess_4 | 01a18a34-fc84-7d50-85dd-c6ce929c7e26 | gpt-6.1-sol | medium | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/tess_4-metadata.jsonl:3 |
| 4 | /root/ivan_4 | 01a18a3a-c3de-7790-b33d-ef5afbb42e70 | gpt-6.1-sol | medium | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_4-metadata.jsonl:2 |
| 4 | /root/ivan_4 | 01a18a3a-c3de-7790-b33d-ef5afbb42e70 | gpt-6.1-sol | medium | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_4-metadata.jsonl:3 |
| 5 | /root/ivan_5 | 01a18a47-8cda-7332-9484-9f88813e5493 | gpt-6.1-sol | medium | docs/dev/project-management/autopilot/reports/00110-backup-plan-preview-and-output-resolution-v1-evidence/ivan_5-metadata.jsonl:2 |

Tasks1/2/3 API changes classified logical opus. Native mapping gpt-6.1-sol/high; concrete task2 style-lint and task3 type/path defects triggered bounded gpt-6-astra/high repair groups, retained as separate attempts without changing logical tier. Tasks4/5 are Sonnet mapped gpt-6.1-sol/medium. Both test writers and contributing implementation/repair sessions are included. Task4 fixture correction and its complexity repair remain within the same Sonnet group. Task2 style_2 initial extraction contributed; its interrupted follow-up had no edits and is not separately cited.

Commit correlation: task1 tests773b2d1f/5975d208 and implementatione77766fc; task2 tests6a172d2f/99f5c64a and implementation091cf6d8/de84f6f1; task3 tests5d33b702/428e29d3 and implementation0a6aea45; task4 testsf41223a3/40d07202 and implementation829517a1; task5 docsa7141346. Full dispatch ids, gates and findings are in the sibling build report and durable dispatch ledger.

Excluded: coordinator/planning/report prose, guardian approval models, Qwen one-token infrastructure preflight, restored Devon adversarial implementations, noop cleanup and read-only Pat reviews. Source Qwen route was replaced before dispatch because host review mapping is unsupported. Source external interception for task5 was disabled by real unhealthy hook doctor before any live model probe or external implementation. No unsupported provider contributed code. Legacy implementor/codex_probe labels denote schema/launcher roles and do not establish origin.

All observed contributing models originate at OpenAI. Required independent completion roster is Anthropic Claude Opus/xhigh in cycle1 for Alice, Blake, Bob, preserving full consensus/blind/doubt+de-slop rubrics and isolation. This build session ran no completion lens and claims no completion-review receipt or convergence.

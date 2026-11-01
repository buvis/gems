# PRD 00112 implementation model audit

Fingerprint: `5103205432dd5cf63060d8d7542a79ceabd124724a9c262572681dcbf2ca53e8`. PRD, cycle1 and work_start_sha `853b765e2662d64a8cc2363ac1582228bfc88d90` bind the snapshot.

The native session metadata identifies each isolated child by agent_path and parent thread, with this repository as cwd. Raw turn_context rows prove exact model and high effort; raw session_meta proves provider OpenAI. Each repo-relative copied JSONL retains the actual source bytes. Evidence hashes cover the exact cited line, excluding its newline. Task numbers are correlated with the dispatch prompt, agent path, role report and task-labelled commit range; prompt examples and reviewer model names are not treated as provenance.

| Task | Work range | Observed contributing models |
|---|---|---|
| 1: Add ProgressEvent record | `853b765e..cfba016f` | `gpt-6.1-sol` |
| 2: Emit archive engine progress | `cfba016f..042ea625` | `gpt-6-astra`, `gpt-6.1-sol` |
| 3: Deliver runner progress on calling thread | `042ea625..17b8ff67` | `gpt-6-astra`, `gpt-6.1-sol` |
| 4: Render live progress and quiet mode | `17b8ff67..92226ceb` | `gpt-6.1-sol` |
| 5: Document live progress and quiet | `92226ceb..1014e6c7` | `gpt-6-astra`, `gpt-6.1-sol` |

Tess authors, quality/style corrections, adversarial strengthening, initial Ivan implementations, bounded Astra repairs and the task4 docstring repair are included. Initial sol contributions remain in history even where a later Astra repair completed the task. Tasks2/3 escalated after concrete precommit lint failures; task5 after reversed fallback wording. Logical tier remains opus; actual provider/model and native launcher remain separate.

Planning/design workers, the coordinator, read-only Pat/design reviewers, noop self-deslop and the no-edit hygiene adjudicator are excluded. Devon temporary mutants were restored byte-for-byte and contributed no retained implementation; their proof reports remain durable. No Gemini implementation dispatched: the source UI route lacked independent review support, so the host-authorized native fallback ran before implementation.

Both observed GPT models map to OpenAI by the verified driver mapping. Required fresh completion roster: Anthropic Claude Opus/xhigh for Alice, Blake and Bob, each isolated and reviewing the whole change. No completion lens ran in this build session.

## Evidence correlation

- Task1, test-author: `gpt-6.1-sol` / high; [00112-task-1-tess1-session.jsonl](00112-task-1-tess1-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-36-41-01a198d4-1fa0-7241-a000-eb14748deca2.jsonl`.
- Task1, test-strengthener: `gpt-6.1-sol` / high; [00112-task-1-tess1_strengthen-session.jsonl](00112-task-1-tess1_strengthen-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-40-51-01a198d7-f122-7471-89a5-06ab7e2f98cb.jsonl`.
- Task1, implementor: `gpt-6.1-sol` / high; [00112-task-1-ivan1-session.jsonl](00112-task-1-ivan1-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-42-21-01a198d9-52a2-7b63-b71b-a496f3202e83.jsonl`.
- Task2, test-author: `gpt-6.1-sol` / high; [00112-task-2-tess2-session.jsonl](00112-task-2-tess2-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-43-54-01a198da-bcaa-76a3-8063-79225327b326.jsonl`.
- Task2, test-quality-repair: `gpt-6.1-sol` / high; [00112-task-2-tess2_quality-session.jsonl](00112-task-2-tess2_quality-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-47-29-01a198de-0530-7022-ab77-ebc7e796bc9b.jsonl`.
- Task2, test-style-repair: `gpt-6.1-sol` / high; [00112-task-2-tess2_style-session.jsonl](00112-task-2-tess2_style-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-49-28-01a198df-d6db-7613-a1ac-4566af19494a.jsonl`.
- Task2, test-strengthener: `gpt-6.1-sol` / high; [00112-task-2-tess2_strengthen-session.jsonl](00112-task-2-tess2_strengthen-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-53-23-01a198e3-6b49-70d3-874e-8ae062dce003.jsonl`.
- Task2, implementor: `gpt-6.1-sol` / high; [00112-task-2-ivan2-session.jsonl](00112-task-2-ivan2-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-56-13-01a198e6-0491-78e1-8932-42f883b99c53.jsonl`.
- Task2, implementor-repair: `gpt-6-astra` / high; [00112-task-2-ivan2_retry-session.jsonl](00112-task-2-ivan2_retry-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T21-59-32-01a198e9-0d0f-7463-9a91-b4ae7ff79df5.jsonl`.
- Task3, test-author: `gpt-6.1-sol` / high; [00112-task-3-tess3-session.jsonl](00112-task-3-tess3-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-06-03-01a198ef-055d-76b1-98d8-2a897c19eae9.jsonl`.
- Task3, test-quality-repair: `gpt-6.1-sol` / high; [00112-task-3-tess3_quality-session.jsonl](00112-task-3-tess3_quality-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-13-26-01a198f5-c5c1-7062-9775-fad65ddac512.jsonl`.
- Task3, test-strengthener: `gpt-6.1-sol` / high; [00112-task-3-tess3_strengthen-session.jsonl](00112-task-3-tess3_strengthen-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-19-08-01a198fb-0038-7b01-bde5-592e2464cab6.jsonl`.
- Task3, implementor: `gpt-6.1-sol` / high; [00112-task-3-ivan3-session.jsonl](00112-task-3-ivan3-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-21-33-01a198fd-33c0-7473-add8-0b52249fd26f.jsonl`.
- Task3, implementor-repair: `gpt-6-astra` / high; [00112-task-3-ivan3_retry-session.jsonl](00112-task-3-ivan3_retry-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-25-21-01a19900-af79-7123-bbfd-55dabe96090b.jsonl`.
- Task4, test-author: `gpt-6.1-sol` / high; [00112-task-4-tess4-session.jsonl](00112-task-4-tess4-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-30-01-01a19904-f4b8-7072-a334-23a4562c4d7d.jsonl`.
- Task4, test-strengthener: `gpt-6.1-sol` / high; [00112-task-4-tess4_strengthen-session.jsonl](00112-task-4-tess4_strengthen-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-40-12-01a1990e-4784-7703-8269-95cd6d2b0650.jsonl`.
- Task4, test-quality-repair: `gpt-6.1-sol` / high; [00112-task-4-tess4_quality-session.jsonl](00112-task-4-tess4_quality-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-43-50-01a19911-9d1d-7123-9b3c-3a61850a9b53.jsonl`.
- Task4, implementor: `gpt-6.1-sol` / high; [00112-task-4-ivan4-session.jsonl](00112-task-4-ivan4-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-45-07-01a19912-c8c6-7253-8d5d-a500641a37de.jsonl`.
- Task4, implementation-doc-fix: `gpt-6.1-sol` / high; [00112-task-4-ivan4_doc-session.jsonl](00112-task-4-ivan4_doc-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-52-15-01a19919-50f5-73f3-b8ae-dc1801373085.jsonl`.
- Task5, documentation-implementor: `gpt-6.1-sol` / high; [00112-task-5-ivan5-session.jsonl](00112-task-5-ivan5-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-53-31-01a1991a-7acb-7391-a53a-65f225e626c8.jsonl`.
- Task5, documentation-repair: `gpt-6-astra` / high; [00112-task-5-ivan5_retry-session.jsonl](00112-task-5-ivan5_retry-session.jsonl) line10; original `/Users/bob/.codex/sessions/2026/11/01/rollout-2026-11-01T22-55-04-01a1991b-e4be-7f90-aeb5-0daf7243b244.jsonl`.

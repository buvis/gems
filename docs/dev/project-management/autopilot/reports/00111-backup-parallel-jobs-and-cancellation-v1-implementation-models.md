# Implementation model audit

PRD 00111-backup-parallel-jobs-and-cancellation-v1.md; cycle 1; work base 9a7f78c8eb0e4148181584f92eb649cfec590034.
All contributing sessions are OpenAI. Logical opus uses gpt-6.1-sol/high;
concrete failed checks triggered bounded gpt-6-astra/high repairs. Attempts
retain launcher identity separately as codex. No alias or prompt model name
was treated as served-model evidence.

The JSON cites original model-bearing turn_context line bytes. Metadata excerpts
retain session_meta (worker path, session ID, parent and start commit), actual
turn_context, and available thread-settings/task-completion events. Correlate
worker names with dispatch IDs in 00111-build-session-progress.md and the durable
dispatch ledger. Both task5 turns are retained. Repeated identical model rows
reflect distinct observed worker turns, not guessed extra contributors.

| Task | Worker | Session | Observed model | Raw metadata |
|---|---|---|---|---|
| 1 | /root/ivan1_astra | 01a18c4d-63d9-74c3-83bb-dc92173f16f2 | gpt-6-astra | 00111-task-1-ivan-astra-model-metadata.jsonl |
| 1 | /root/ivan1 | 01a18c49-2787-7320-94bc-f259ba722505 | gpt-6.1-sol | 00111-task-1-ivan-sol-model-metadata.jsonl |
| 1 | /root/tess1 | 01a18c38-fe26-7191-a584-63714a307c90 | gpt-6.1-sol | 00111-task-1-tess-model-metadata.jsonl |
| 1 | /root/tess1_strengthen | 01a18c46-450a-7871-a8e6-876685393896 | gpt-6.1-sol | 00111-task-1-tess-strengthen-model-metadata.jsonl |
| 2 | /root/tess2 | 01a18c54-1211-7490-b364-eaa04fb32f6e | gpt-6.1-sol | 00111-task-2-tess-model-metadata.jsonl |
| 2 | /root/tess2_retry2 | 01a18efd-8e9c-7362-bcca-b0edc6dd19f5 | gpt-6.1-sol | 00111-worker-01a18efd-8e9c-7362-bcca-b0edc6dd19f5-metadata.jsonl |
| 2 | /root/tess2_strengthen | 01a18f01-dfbd-7ed2-b852-7df2cc134eea | gpt-6.1-sol | 00111-worker-01a18f01-dfbd-7ed2-b852-7df2cc134eea-metadata.jsonl |
| 2 | /root/ivan2 | 01a18f02-f071-7d32-9e68-1eba07667d8e | gpt-6.1-sol | 00111-worker-01a18f02-f071-7d32-9e68-1eba07667d8e-metadata.jsonl |
| 2 | /root/ivan2_repair | 01a18f06-87f0-7852-b6d9-1e329ac76366 | gpt-6-astra | 00111-worker-01a18f06-87f0-7852-b6d9-1e329ac76366-metadata.jsonl |
| 2 | /root/ivan2_final_regression | 01a18f22-0de4-71c0-981f-c6a7c67ea04c | gpt-6-astra | 00111-worker-01a18f22-0de4-71c0-981f-c6a7c67ea04c-metadata.jsonl |
| 3 | /root/tess3 | 01a18f09-c6c1-7312-a3d8-72e383d58128 | gpt-6.1-sol | 00111-worker-01a18f09-c6c1-7312-a3d8-72e383d58128-metadata.jsonl |
| 3 | /root/tess3_strengthen | 01a18f11-bf65-7610-8850-3ddaddf172db | gpt-6.1-sol | 00111-worker-01a18f11-bf65-7610-8850-3ddaddf172db-metadata.jsonl |
| 3 | /root/ivan3 | 01a18f14-dd62-7b22-a484-d2af75f2fff6 | gpt-6.1-sol | 00111-worker-01a18f14-dd62-7b22-a484-d2af75f2fff6-metadata.jsonl |
| 3 | /root/tess3_correction | 01a18f17-6cd6-7091-8236-39aef9e5d843 | gpt-6.1-sol | 00111-worker-01a18f17-6cd6-7091-8236-39aef9e5d843-metadata.jsonl |
| 3 | /root/ivan3_repair | 01a18f19-340e-7e70-8fb6-3619d14f51c0 | gpt-6-astra | 00111-worker-01a18f19-340e-7e70-8fb6-3619d14f51c0-metadata.jsonl |
| 3 | /root/ivan3_final_regression | 01a18f23-ef76-7d30-8ba3-267820ccc5fe | gpt-6-astra | 00111-worker-01a18f23-ef76-7d30-8ba3-267820ccc5fe-metadata.jsonl |
| 4 | /root/ivan4 | 01a18f1a-d487-71e2-85f0-defa6a880626 | gpt-6.1-sol | 00111-worker-01a18f1a-d487-71e2-85f0-defa6a880626-metadata.jsonl |
| 5 | /root/ivan5 | 01a18f1b-e4a1-7d93-9b7f-9256b97f5fe4 | gpt-6.1-sol, gpt-6.1-sol | 00111-worker-01a18f1b-e4a1-7d93-9b7f-9256b97f5fe4-metadata.jsonl |

Task1: Tess initial/strengthen tests cd40e4e3/61501bd9, Sol contribution and
Astra final repair 455c9cba. Task2: original draft author, style/tuple correction
fa3c8070/3bce4ede, Sol and Astra implementation 6ce10911, final-verification
test-contract correction 3b9c3bc4. Task3: Tess initial/strengthen/fixture
correction dbaba0fa/c969888d/1ddb42e7, Sol and Astra implementation e3b4d55f,
final-verification generator-mock correction 9541edc4. Task4 guide 9aeead53.
Task5 README a1505c1d and terminology correction 4d3dc43e.

Excluded from implementors: planning/design, coordinator and host diagnostics,
Tess2's abort before edits, temporary Devon candidates restored byte-for-byte,
no-op self-deslop and failed quota-limited Pat reviews. Host verification
environment wrappers change no product implementation or test assertions.
Test writers, repairs and every prior contributing attempt remain included.
No unsupported-provider contribution, unknown family or auto-model ambiguity.

Independent review route: Anthropic Opus/xhigh Alice, Blake and Bob, each over
the whole change in a fresh process. Completion review did not run in this build
session. Regenerate this fingerprint before every review cycle; ordinary rework
changes provenance. No reviewed snapshot or receipt was replaced.

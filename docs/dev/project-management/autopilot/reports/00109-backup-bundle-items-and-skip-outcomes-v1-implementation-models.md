# Implementation model audit

PRD `00109-backup-bundle-items-and-skip-outcomes-v1.md`, task `1`, card `00109-backup-bundle-items-and-skip-outcomes-v1-c1`, attempt 1, cycle 1.
Work starts at `5a3ab34deb025e2a4223f9af876ec0256c2de177`.

Both contributors are native OpenAI `gpt-6.1-sol`, high effort, logical opus. The PRD explicitly selects opus for its selection algorithm and shared exit contract. No failed contributing implementation attempt, model switch, or provider fallback exists.

Tess `/root/tess`, session `01a189e3-fda3-7f33-a75e-a79c274a1805`, dispatch `f136dd3d`, wrote the tests committed as `877afe2d`. Ivan `/root/ivan`, session `01a189ea-2b25-7660-b52b-8e814f9d387a`, dispatch `328ad5f6`, implemented production and documentation committed as `3d4d2cd4`. Their exact raw session_meta and turn_context records are copied into `00109-tess-model-metadata.jsonl` and `00109-ivan-model-metadata.jsonl`. Session metadata binds agent_path, parent thread, session identity and provider; turn_context records observed model and effort. The JSON audit hashes each cited raw turn_context line. The requested settings agree with observed metadata.

Source raw logs: `/Users/bob/.codex/sessions/2026/10/29/rollout-2026-10-29T23-59-42-01a189e3-fda3-7f33-a75e-a79c274a1805.jsonl` and `/Users/bob/.codex/sessions/2026/10/30/rollout-2026-10-30T00-06-27-01a189ea-2b25-7660-b52b-8e814f9d387a.jsonl`. The audit cites repository-local immutable copies so evidence is available remotely. Dispatch-ledger rows correlate card, prompt byte count and completion. Coordinator, approval guardian and read-only reviewer models are excluded.

Task attempt fields retain launcher `codex` separately from actual provider `openai`; test-writer provenance is retained too. Both evidence rows are included even though they name the same model. The fingerprint and snapshot were computed using the installed host driver. `review-route` validates this audit and returns Anthropic. No completion reviewer ran in this build session.

The native source worker route has independent Anthropic review support in the host driver; no unsupported provider route was selected. Host adapters override the in-session fast-track roster: completion review must use fresh Alice, Blake and Bob with complete rubrics and host receipts in a fresh review process. No lane_reviewed transition or review-completion claim is made here.

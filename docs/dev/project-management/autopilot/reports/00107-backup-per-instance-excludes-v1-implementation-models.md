# Implementation model audit

Task 1 is the single rendered card for PRD 00107. Both contributing roles ran
at logical sonnet, actual OpenAI `gpt-6.1-sol`, medium effort. The companion JSON
binds PRD, cycle, work base, and attempt provenance with the host driver's
`implementation_fingerprint` and `implementation_snapshot` functions.

Evidence is copied byte-for-byte from the native worker session logs, not model
names appearing in instructions or reviewer output. In each copied JSONL,
line 1 is `session_meta` identifying the agent path and session, and line 10 is
the observed `turn_context` containing model and effort. The JSON audit hashes
the exact bytes of line 10, excluding its newline.

| Role | Agent | Session | Dispatch | Contribution |
|---|---|---|---|---|
| Test author | `/root/tess` | `01a189d7-f5f9-7962-93e8-7b375c13a24c` | `d4993abe` | New specification tests, commit `74e19c78` |
| Implementor | `/root/ivan` | `01a189da-e63e-7032-a541-c532c47c0b8a` | `2029bfe3` | Config, runner, CLI, documentation, commit `182e9bd3` |

Both rows belong to task 1, attempt 1, whose work base is
`4becb45eb3c0949544dfeec5ed3db3424bcbc4d5`. The dispatch ledger records their
start/end events. The task attempt retains launcher identity `codex` separately
from actual model and provider. Tests are implementation contributions and are
included even though their author is independent of Ivan.

No prior contributing attempt, repair, split task, model switch, or fallback
exists. Coordinator inspection, prompt assembly, hook formatting, and read-only
validation do not establish implementation model origin. No completion reviewer
ran during the build session. The required opposite-company review roster is
Anthropic Claude Opus for Alice, Blake, and Bob, using the host helper in a fresh
review session. The audit must be regenerated before each new review cycle.

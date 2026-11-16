# Backlog review - buvis/gems - 2026-11-16

Scope: Tiromex PRDs 00150-00155 on `feature/merge-klyreon-to-bim`. PRDs 00122
and 00123 are out of scope (they belong to `feature/config-local-layer-braid`).

Verdict: GO for 00150 and 00151 (0 Blocking open). 00152-00155 are READY as
text but wait on external preconditions their `eligibility` lines enforce.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00150 | bim tiromex format | standard | 130 | bim tx, bim settings, skill | none | READY (was FIX) |
| 00151 | bim shared LLM backends | standard | 122 | bim shared/llm, bim doc | 00150 done | READY (was FIX) |
| 00152 | bim mirror roots and article migration | standard | 142 | bim shared, create, serve, TUI | 00151 done; `86b758d9` in master and HEAD | READY (was FIX), gated |
| 00153 | bim tx ingest | standard | 141 | bim tx | 00152 done; llama.cpp server on :8080 | READY (was FIX), gated |
| 00154 | bim tx maintain, schedule, interfaces | standard | 142 | bim tx, serve, TUI | 00153 done | READY (was FIX), gated |
| 00155 | retire klyreon | standard | 150 | klyreon, pyproject, docs | 00154 done | READY (was FIX), gated |

## Findings

### Blocking

- [00150-00155] B/C path rule: every Repository Structure tree left out files
  its own Module Locations name (CHANGELOG.md, docs/source/tools/bim.rst,
  src/tools/bim/*.py, and more). `cli/policy.py` counts 2 to 8 unlisted
  modules per PRD against a limit of 1 -> fails as: stall (plan-expansion
  gate, `module_drift`, parks the PRD in loop mode). Fix: appended each
  uncovered Location path to the tree. Verified with the plugin's own
  `policy.prd_modules`: drift is 0 on all six.
- [00153] B executability: live qualification named Ollama `qwen3:30b-a3b`
  (marked guess). Ollama is not installed on this host; `llama-server` is, and
  the host's qualified local model is `unsloth/Qwen3.8-27B-GGUF:UD-Q6_K_XL` on
  `127.0.0.1:8080` (use-qwen skill) -> fails as: unattended hang or rework
  thrash (an acceptance no session can meet). Fix: PRD now names the llama.cpp
  endpoint and model, and `eligibility` also requires that endpoint to answer.
  Discovery allows "Ollama or llama.cpp". The server was down at review time.
- [00155] B executability: Exit Criteria required CI to pass for the removal
  commit. `.github/workflows/test.yml` runs only on pushes and pull requests
  to master, and autopilot opens no pull request -> fails as: rework thrash.
  Fix: CI is recorded as pending in the coverage report, closed by the owner
  after the merge to master, like the host cleanup.

### Non-blocking

- [00151] F sizing: 3 task lines for 16 source files; the expansion rule
  stalls a plan over 9 tasks. Fix applied: split the adapter task in three
  (`-k http`, `-k claude`, `-k command`) and the doc rewire in two. 6 lines.
- [00150, 00152] F sizing: 4 task lines each, so a plan over 12 tasks trips
  the expansion rule. Not changed; the design phase can keep plans under it.
- [00152] B contract: the migration subcommand name is left to design
  (Risks, "Invented CLI spelling"). Not changed; the design phase fixes it
  before tests are written.
- [00150] C mapping: module "Note contract" holds the command files while
  "Integration" maps to "Foundation commands". Readable; not changed.

### Questions

None.

## Reshapes

None.

## Gaps

- 00152-00155 need `feature/config-local-layer-braid` merged to master and
  master merged into this branch (owner action).
- 00153 needs the llama.cpp server running on 127.0.0.1:8080.
- Discovery nice-to-haves (`mirror:` links in `bim show`, Obsidian
  click-through) have no PRD. Intended.

## End state after this batch

bim owns claims, mirrors, one LLM layer, ingest, maintain and schedule under
`bim tx`; klyreon is gone from src, tests, docs and wiring. Still open after
the batch: host cleanup hand-off, CI on master for the removal commit, and
`ConfigWriter.write` remains a bare write (pre-existing, out of scope).

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| all | none | `design: run` and `default_model: opus` fit (equivalence, concurrency) |

## Checks run

- `check_links.py`: only forward references (eligibility targets and two
  report files the PRDs create).
- `ground_prd.py` on the six after edits: 0 blocking, 0 unverified.
- Lens D: `e78fee4c` exists; cited files resolve. Not re-verified by hand:
  each cited line range beyond what `ground_prd.py` checks.
- Not run: the test suite.

## Decisions applied

All fixes above applied in place under standing authorization, no walkthrough.

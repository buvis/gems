HOST TRANSPORT: Use only your read, glob and grep tools. Never use a shell, including git, rg, tests, linters or builds. Do not request shell approval. All required gate results are supplied. This overrides persona shell examples while preserving every review lens and rubric. Read global and repository AGENTS.md and applicable nested instructions. Review only; do not modify files.

Read /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/review-context-00112-c1.md for review context, and /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/review-diff-00112-c1.diff for the full diff.

Read /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/engram-pack-00112-c1.md and treat its full content as prepended context: similar code, reuse precedent, findings precedent, and task prose for this diff's changed symbols.

Use this review checklist:
# Review Dimensions

Detailed checklist for reviewing completed work.

## Plan Compliance

- [ ] Implementation matches task description
- [ ] All acceptance criteria met
- [ ] No scope creep (extra features not requested)
- [ ] No missing pieces from original task

## PRD Coverage

- [ ] All "must have" requirements addressed
- [ ] Success metrics achievable with implementation
- [ ] No PRD sections left unimplemented
- [ ] Dependencies correctly handled

## Simplification

Hunt actively for simplification — do not just tick boxes. The diff under
review is fresh; this is the cheapest moment to cut complexity before it sets.
For every added or changed file, ask "what would make this simpler to read
without changing what it does?" and flag concrete opportunities.

- [ ] **Reduce complexity** — no needless indirection, dead branches, or
      abstractions built for a single caller; nesting <= 4 levels; functions
      under 50 lines
- [ ] **Eliminate redundancy** — no logic duplicated within the diff or against
      existing code; no helper that reimplements a stdlib or existing utility
- [ ] **Improve naming** — names state intent; no opaque abbreviations;
      action-named functions start with a verb
- [ ] **Follow project standards** — conventions from CLAUDE.md / AGENTS.md and
      the surrounding code; no style drift
- [ ] **No dead code** — no commented-out blocks, unused imports, variables, or
      speculatively-added parameters
- [ ] **Appropriate error handling** — explicit, never silently swallowed

**How to flag a simplification:** give the file:line, the current shape, and
the simpler replacement. Flag concrete behavior-preserving simplifications at
🟡 Medium so the decision gate routes them into the rework loop. Do not inflate
them to 🟠 High; that floods the rework loop and can trip the scope alarm.

**Balance — do not over-simplify:** never propose a change that trades clarity
for brevity, drops error handling, collapses a deliberate boundary, or removes
a documented invariant. Simpler means easier to read and maintain, not shorter
at any cost. If a "simplification" would change behavior, it is out of scope —
do not flag it.

## Testing

- [ ] Unit tests for new logic
- [ ] Edge cases covered
- [ ] Error paths tested
- [ ] Integration tests if crossing boundaries
- [ ] Tests actually run and pass
- [ ] No tautological test — every new or changed test fails against the
      pre-change code (the context's fail-first replay block), and no assert
      is constant, self-comparing, or an either-or hedge (the shapes block)

## Security

- [ ] No hardcoded secrets
- [ ] Input validation at boundaries
- [ ] No SQL/command injection risks
- [ ] Auth/authz correctly applied
- [ ] Sensitive data not logged

## Documentation

- [ ] Public APIs documented
- [ ] Complex logic has comments
- [ ] README updated if needed
- [ ] Breaking changes noted

In addition, work through the numbered rubric:
# Review-Work-Completion Rubric

This rubric defines binary pass/fail criteria for consensus review of completed work. Each rule is numbered and stable for tracking coverage. Reviewers must answer "R{n}: pass|fail" for every rule in their prompt.

## Rules

### Tests

R1: Tests cover every new behavior introduced by the diff.
R2: Tests bind to intent, not just observable behavior; no new or changed test is tautological (passes against the pre-change code, or cannot fail as written).
R3: No skipped or xfail tests mask failures.

### Integration

R4: Changed components integrate with existing callers.

### Security

R6: No hardcoded secrets in the codebase.
R7: All user input is validated and sanitized.
R8: No injection-unsafe queries or commands.

### Domain

R9: Implementation matches PRD feature behavior exactly.
R10: Error handling is explicit and not swallowed.
R11: No debug statements, TODOs, or placeholder markers remain.

### Code Quality

R12: Function sizes respect the 50-line limit.
R13: File sizes respect the 800-line limit.

Review the completed work against PRD requirements. Explore the codebase as needed.

OUTPUT FORMAT IS MANDATORY. Follow exactly:
## Agent Output Format (Single Source of Truth)

Each agent outputs issues in this exact format:

```
[{AGENT_NAME}] {emoji} {description} | File: {path or "N/A"} | Task: {id or "general"}
```

**Severity emojis:** 🔴 Critical, 🟠 High, 🟡 Medium, ⚪ Low

**Rules:**
- One issue per line
- Use "N/A" for file if issue is architectural/cross-cutting
- Use "general" for task if issue spans multiple tasks or is a PRD gap
- If zero issues found: `[{AGENT_NAME}] ✅ No issues found`

**Examples:**
```
[ALICE] 🔴 SQL injection in query builder | File: src/db/query.ts | Task: 3
[BOB] 🟠 Missing error handling strategy | File: N/A | Task: general
[CARL] 🟡 PRD section 2.3 not implemented | File: N/A | Task: 5
```

Your agent name is BOB.

PER-RULE VERDICTS ARE MANDATORY. For every rule in the numbered rubric, emit one line:
R{n}: pass   or   R{n}: fail
(one rule per line, no other text on the line, no rationale).

## Sandbox Constraints

You run in a read-only sandbox. Read files with your read tool; that is how you open /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/review-context-00112-c1.md, /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/review-diff-00112-c1.diff, /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/engram-pack-00112-c1.md and any source file. You CANNOT execute code, tests, linters, or package managers, and you cannot write.

Perform STATIC analysis only:
- Read code for logical correctness, patterns, naming, structure
- Check for missing imports, dead code, type mismatches
- Review against PRD requirements by reading, not executing
- Trace data flow and control flow by reading source

If a criterion requires runtime verification (e.g. "tests pass", "linter clean"), output:
[BOB] ⚪ Cannot statically verify: {criterion description} | File: N/A | Task: {id}

Do NOT run tests, linters, builds, or package managers. Do NOT report failures from blocked execution. Never report an inability to read a file you were told to read: read it with your read tool.

## Two lenses, applied to every changed file

Treat - findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  - F4: read `MACHINE_PATH` (`checks.py:89-92`). The `/` branch requires at least one `segment/`, so `/tmp` and `/config.json` never match, and `$HOME` has no branch.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  - F1: each of the three guard tests seeds a defect in the same file after its no-finding assertion. Mutation at `ba8e7b8`: with `closed_fences`, `portable_links` and `requirement_source` returning `[]`, all three tests fail.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00007-reviews-and-conversion-review-01.md
  - F7: accepted (ledger entry added). The T-077 outcome records the copy as a choice: each scan runs standalone by `python3 <path>`.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  # Review: 00012-autopilot-package-contract-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/tmp/blake-output-ap00012-c1.txt.receipt.json

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  The source's Codex-only inline-input requirement is adapted to the authorized Claude transport: Bob received the complete assembled persona, rubrics and appendices plus readable context/diff paths. His successful raw tool reads establish that the restriction that motivated inline-only Codex prompts does not apply. The 45 MB full diff was not truncated into a prompt. No implementation thread was resumed.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  Provider: Anthropic; served model claude-opus-5-5; effort xhigh; session 95ff83bd-845a-4d23-9d77-2b8ff0ab183b.

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00009-walk-memory-proposal-queue-v1-review-1.md
  # Review: 00009-walk-memory-proposal-queue-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00051-qwen-eval-harness-core-v1-review-1.md
  ### Classification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00051-qwen-eval-harness-core-v1-review-2.md
  ### Adversarial verification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00058-page-links-accept-javascript-urls-v1-review-1.md
  Fact-Forcing Gate (`gateguard`) — `error=Command blocked by PreToolUse hook:

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-03.md
  ```

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00182-close-open-dispatch-rows-at-session-handoffs-v1-review-2.md
  `5ebd59c`, `6273c54`, `9d6bdef`, `5a5daa8`, `a026540`. Cycle 1 reviewed the full as findings precedent already recorded for this diff's changed symbols. Weigh it when applying both lenses and the rubric verdicts rather than re-litigating known prior findings.

### 1. Doubt lens (correctness)
Surface residual findings a confident reviewer would wave past:
- spec gaps: PRD says X, code does Y (wrong field names, enum values,
  thresholds, artifact kind);
- missing or incomplete features the PRD requires;
- edge cases, error paths, and failure modes left unhandled;
- tests that cannot fail: they assert the implementation rather than the intent,
  or still pass against the pre-change code (the caller's mechanical test checks
  list every one it found; each is behavior left unpinned).

### 2. De-slop lens (quality)
Flag slop introduced by the changes (do not propose broad refactors):
- over-abstraction / single-caller indirection with no current testability or
  architectural need;
- dead code, code kept in comments, unreachable branches;
- defensive guards for states that cannot occur;
- restating docstrings, "robust" error messages with no context, premature
  configuration, framework-verification tests;
- speculative generality (parameters, hooks, or layers nothing uses yet).
Bias: aggressive on newly-created files (slop concentrates there), conservative
on lightly-touched files (do not destabilize existing behavior).

## Categorize every residual finding

Place EACH finding in exactly one bucket:
- **FIX** — genuinely fixable now: bounded scope, in-scope, actionable.
- **VERIFY** — needs a specific named check to resolve (state the exact check,
  not "look into X").
- **KNOWN** — a real limitation that is out of scope; include a one-line written
  justification.

Output the buckets as three sections, one finding per line:

```
FIX:
- <finding> — <file:line> — <the concrete fix>
VERIFY:
- <finding> — <the exact check to run>
KNOWN:
- <finding> — <why it is out of scope>
```

If a bucket is empty, write the header and `- (none)`.

## Rubric verdicts (REQUIRED — emit verbatim, one per line)

Apply the doubt-review rubric. A rule you cannot evaluate is `fail`; never omit
a line.
- D1: every residual finding is in exactly one of FIX/VERIFY/KNOWN.
- D2: all FIX items are genuinely fixable now (bounded, in-scope, actionable).
- D3: all VERIFY items name the exact check needed (not vague).
- D4: all KNOWN items carry a written out-of-scope justification.
- D5: input finding count equals FIX + VERIFY + KNOWN counts.

Emit exactly:

```
D1: pass|fail
D2: pass|fail
D3: pass|fail
D4: pass|fail
D5: pass|fail
```

Do not modify any files. This is a review only — produce findings and the
rubric verdict lines. No commits.

Cite files repo-relative as path:line (for example skills/work/SKILL.md:166), never absolute and never with a "(lines a-b)" suffix.

Transport reminder: use read/glob/grep tools only; never a shell. The supplied full-suite gate is authoritative.

Full diff includes durable workflow telemetry; inspect all production and test changes with read/grep tools. Full diff is retained without truncation.

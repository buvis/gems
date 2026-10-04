# postup G2: brief-portfolio cutover

<!-- requirements; migrated from PRD 00070 flat file -->

## Overview

### Problem Statement
The `brief-portfolio` skill (`~/.claude/skills/brief-portfolio/`) is the parallel implementation of the portfolio brief that postup was built to replace. Until it retires, two collectors read the same repos and answer the same question with two codebases that will drift. Deleting it on faith is the wrong move: the skill is live and in use, so the cutover needs evidence that postup covers every signal the skill produces before anything is removed.

### Target Users
Solo developer reading the portfolio brief; repo hygiene (one brief, one implementation).

### Success Metrics
- A recorded parity artifact shows postup's collector covering every per-repo signal field the skill's collector produces, over the same portfolio snapshot.
- A signal field present in the skill's output and absent from postup's fails the check and blocks cutover — demonstrated by a negative fixture, not just asserted.
- The skill-deletion instructions are recorded in the PRD's completion notes with an execution-time premise re-check, and correctly describe the removal as a buvis-tracked `git rm`, not a plain `rm -rf`.
- CHANGELOG carries the cutover note; gems gates green.

## Functional Decomposition

### Capability: Cutover
Retire the parallel brief implementation, with evidence.

#### Feature: Data-level parity check
- **Description**: The gate before skill deletion, as defined by discovery review F2.
- **Inputs**: The same portfolio snapshot collected by both the skill's `scripts/collect.py` and `postup collect` (postup roots/excludes configured to match the skill's gita-derived repo set for the comparison).
- **Outputs**: A recorded parity checklist as a `dev/local/` artifact: same repo set, same per-repo signal fields covered — semantic diff with naming/shape mapping allowed.
- **Behavior**: A signal field present in the skill's output but absent in postup's fails the check and blocks cutover. Narrative and epic *content* are excluded (LLM nondeterminism); enrichment presence is compared only structurally (a schema-valid `epics.json` exists). The comparison is a test-suite fixture pair plus one real-portfolio run, so the rule is exercised headlessly and the real run only produces the recorded artifact.

#### Feature: Skill deletion follow-up
- **Description**: Document the out-of-gems deletion step.
- **Inputs**: Premise: `~/.claude/skills/brief-portfolio/` still exists and postup replaces it. Re-check at execution time (the skill is live and may have changed since discovery): the parity check passed against its current state.
- **Outputs**: A documented follow-up step in this PRD's completion notes. Grounded 2026-07-13, re-confirmed 2026-08-07: this directory **is tracked** by the buvis bare repo (`git --git-dir=~/.buvis ls-tree -r --name-only HEAD -- .claude/skills/brief-portfolio` lists its files; `ls-files` is unreliable here — the bare repo's index is empty, so it returns empty for tracked files too). Removal is therefore `git --git-dir=~/.buvis --work-tree=~ rm -r .claude/skills/brief-portfolio`, then a conventional commit and push. Note that trend/diff history restarts fresh (no legacy migration, per discovery).
- **Behavior**: The deletion itself is a manual out-of-gems action by the user — this PRD ships the evidence and the instructions, not the `rm`. If the premise re-check fails, skip and report; never force.

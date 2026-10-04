# postup G2: brief-portfolio cutover

<!-- tasks; migrated from PRD 00070 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: The comparison rule, tested.

**Tasks**:
- [ ] `compare()` plus fixture pair covering a matching output and a postup output missing one signal field (no deps) - Acceptance: the matching pair passes; the missing-field pair fails and names the exact absent field; narrative and epic content differences do not fail the check while a missing `epics.json` does.

**Exit Criteria**: The parity rule passes and fails for the right reasons on fixtures.

### Phase 1: Core
**Goal**: Evidence from the real portfolio.

**Tasks**:
- [ ] Run the comparison over the real portfolio with postup configured to the skill's gita-derived repo set; write the checklist to `dev/local/audit-results/` (depends on: Phase 0) - Acceptance: the artifact exists, lists the repo set used, and shows full signal-field coverage or names every gap; a genuine repo-set difference is recorded as a config note rather than a parity failure.

**Exit Criteria**: A recorded parity artifact exists and shows full coverage.

### Phase 2: Integration
**Goal**: One brief implementation left.

**Tasks**:
- [ ] Write the skill-deletion follow-up into the completion notes with its execution-time premise re-check and the buvis-tracked `git rm` instruction; add the CHANGELOG entry (depends on: Phase 1) - Acceptance: completion notes carry the premise re-check, the exact `git --git-dir=~/.buvis --work-tree=~ rm -r` command, and the fresh-history note; CHANGELOG records that postup supersedes the brief-portfolio skill.

**Exit Criteria**: Success Metrics hold; postup is the only portfolio-brief implementation, and the skill's removal is a documented one-command step for the owner.

# klyreon D: autonomous maintenance, report-only pruning, scheduler

<!-- tasks; migrated from PRD 00077 flat file -->

## Implementation Phases

### Phase 0: Foundation
**Goal**: The derived graph and the scheduler artifacts, both pure.

**Tasks**:
- [ ] `maintain/graph.py`: one pass building inbound links, corroborating sources, and open disagreements (deps: PRD A spec engine) - Acceptance: fixture vault test asserts each view; a `disagreement` doubt whose `target` names zettel X counts against X even though the doubt lives in Y.
- [ ] `schedule/launchd.py` and `schedule/cron.py` renderers (no deps) - Acceptance: the rendered plist parses as a plist and carries the label, the calendar interval, the `/bin/sh -c` command with a semicolon, and an explicit `PATH`; the rendered cron line carries the marker comment, the absolute binary path, and `PATH=`; both render off-platform so tests run on any OS.

**Exit Criteria**: Graph views and artifact renderers are tested without touching a real scheduler.

### Phase 1: Core
**Goal**: The rules, the prune, and the platform install.

**Tasks**:
- [ ] `maintain/rules.py`: lifecycle and assent planners (depends on: Phase 0) - Acceptance: table-driven tests, one row per rule and per blocked case; an open disagreement holds assent; a promotion never sets `processed: false`; two corroborations from the same source document do not reach `accepted`.
- [ ] `maintain/moc_sync.py`: plan and apply membership reconciliation inside the marker block (depends on: Phase 0) - Acceptance: a zettel added to a MOC's `mocs` appears in that MOC's block after a sweep; a zettel that dropped the anchor and one whose file was removed both disappear from it; human prose above and below the block survives; a MOC named by a zettel but missing from disk is reported as a lint finding and not created; a second sweep plans no change.
- [ ] `maintain/prune.py`: candidate detection with both exemptions, and the grouped delete plus inbound and MOC cleanup (depends on: Phase 0) - Acceptance: backdated fixtures produce exactly the expected candidate set; a `rejected` zettel and a `delivered-as` zettel are exempt; pruning one zettel removes every inbound `links` entry, every `doubts[].target` naming it, and its MOC membership, in one commit, and the vault validates clean.
- [ ] `schedule/installer.py`: platform dispatch, `launchctl bootstrap`/`bootout`, crontab read-strip-append, manifest recording, unsupported-platform failure (depends on: Phase 0) - Acceptance: subprocess-mocked tests for install, re-install, status, and uninstall on both platforms; a second install leaves exactly one marked crontab line and one label; Windows fails with the manual equivalent named.

**Exit Criteria**: Every rule and every scheduler branch is covered.

### Phase 2: Integration
**Goal**: The autonomous loop closes.

**Tasks**:
- [ ] `maintain/sweep.py` plus `CommandMaintain` and the CLI: lock, autonomy gate, lint, transitions, MOC sync, prune, trail, `last_maintain`, `--dry-run` (depends on: Phase 1) - Acceptance: a sweep over the fixture vault applies the expected transitions and MOC reconciliations and writes one `kind: trail`, `run: maintain` file naming both; a second sweep changes nothing; a sweep interrupted after the third commit leaves a `validate`-clean vault and the re-run finishes the rest; `--dry-run` writes nothing at all; a non-git vault refuses with exit 1.
- [ ] `klyreon schedule install|status|uninstall` wired through the CLI; `init` gains the offer (depends on: Phase 1) - Acceptance: install then status reports present, loaded, hash-matched; an edited artifact is reported, not rewritten; uninstall leaves no artifact and no manifest entry; init with `--no-input` skips and prints the follow-up command.
- [ ] Extend `klyreon status` with prune candidates and maintenance freshness (depends on: Phase 1) - Acceptance: candidate count matches the prune rule on backdated fixtures and states whether deletion is enabled.
- [ ] Docs sections, CHANGELOG Added entry, mypy strict, ruff, coverage (depends on: Phase 1) - Acceptance: all gems gates green in CI.

**Exit Criteria**: Every Success Metric above holds against the fixture corpus, headlessly — including the criterion-4 stand-in (a scheduled run over the mixed corpus completing with zero human input, `validate` clean, no hang, and `status` showing mean links per zettel and the `literature`+`evergreen` count higher at the end than at the start). Discovery's literal criterion 4, a live cron run of at least 7 days on the real vault, is a documented post-merge soak the owner runs after `schedule install`; it is not a gate on this PRD.

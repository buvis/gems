# Backlog review - buvis-gems - 2026-10-12

Verdict: NO-GO (2 Blocking open)

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00089 | dot-pull-divergence-report-v1 | standard | 261 | dot: git/service, commands/pull, commands/status, tui, new divergence.py | 00088 (done), **00090 (higher number)** | RESHAPE (renumber) + FIX |
| 00090 | dot-host-links-localize-pull-rescue-v1 | standard | 259 | dot: hostlinks, commands/localize, commands/pull, git/service, tui, cli; pybase console `choose` | 00088 (done) | READY after minor edits |
| 00091 | dot-host-links-setup-v1 | standard | 188 | dot: git/service, commands/setup, status, settings, cli | 00088 (done) | READY |

Mechanical checks (step 1):

- `check_links.py`: 0 findings under `prds/backlog/` or `prds/wip/`. The script exits 1 on out-of-scope files only (`research/00062`, old reviews, specs, and `designs/00088-...-design.md:3`, which cites the PRD at its old `prds/wip/` path).
- `ground_prd.py`: 193 rows over the three PRDs: 106 `ok`, 87 `declared-new`, 0 `missing` / `unresolved` / `unverified`. Caveat: 00089 passes partly by declaring 00090's symbols (`fetch`, `has_upstream`, `plan_rescue`, `CommandLocalize`, `RescuePlan`) as its own new symbols, so the pass is vacuous until 00090 lands.
- Hygiene: only three `NNNNN-{slug}-v1.md` files in `backlog/`; numbers unique across backlog/wip/done/hold (the intake dirs `00088-...` and `00089-...` share numbers with their PRDs by design; no `discovery/` dir in this repo); `wip/` and `hold/` empty.
- Batch state: `autopilot/state.json` batch 202610121200 is live (`next_phase: build`, 00088 completed, no pinned queue). Phase 0 picks the lowest backlog number per session, so a renumber takes effect at the next selection. `session-brief.md` / `contract-card.md` say "next: selects 00089"; both are regenerated per session.
- Law loaded from `~/.agents/skills/create-prd/SKILL.md` + `assets/standard.md`; budget/tier rules from `autopilot` plugin 0.9.0 `plan-tasks` steps 4.5-4.7 (150K per-task threshold, `default_model` floor).

## Findings

### Blocking

- [00089] E collisions, order break: lines 9-11 say "Lands after 00088 and 00090: it reuses 00090's `fetch()`, `has_upstream()`, `CommandPull` rescue flow and two-host test setup", and the Phase 1 premise `rg -n "def fetch|def has_upstream" src/tools/dot/git/service.py` (expect 2) has 0 hits today. Autopilot drains ascending, so 00089 is selected before 00090 -> fails as: stall (the premise check trips and the task stops), and case (5) of the two-host test cannot exist without 00090's `CommandLocalize`. Fix: renumber 00089 -> 00092 (`mv` inside `backlog/`), update the 00090 Risks reference and the capsule's Active Work list. Order becomes 00090, 00091, 00092; 00091 is independent of 00090.
- [00089] D grounding, stale since 00088 landed (the PRD was written against the pre-00088 tree): (a) Phase 2 task 2 premise `rg -n "def _mock_git_ops" tests/tools/dot` (expect 2): actual count is 3 (`test_tui_app.py:11`, `test_tui_host_links.py:14`, `test_tui_snapshots.py:52`), and the task says "if the count differs, stop and report" -> fails as: stall. (b) Module "dot commands and TUI" exports `StatusBar.update_info(info, error=None, pending=None)`; the live signature is `update_info(info, error=None, link_problems=0)` (`status_bar.py:26`, added by 00088). Tests written from the PRD text drop `link_problems` -> wrong-TDD lock-in and rework thrash against 00088's tests. (c) Phase 2 task 2 says "`CommandStatus` stores `dotfiles_root`"; it already does (`status.py:25`). Fix: `MainScreen` already holds `self._dotfiles_root` (`main.py:117`, 00088), so `refresh_status` passes `pending_patch_warning(self._dotfiles_root) if self._dotfiles_root else None` and the mock-helper premise is dropped; export `update_info(info, error=None, link_problems=0, pending=None)`; drop the "stores" clause.

### Non-blocking

- [00089, 00090] B/D TUI diff-pane assertions: 00088's run deferred a pre-existing bug (`autopilot/deferred/202610121200-deferred.json`, `main.py:181`): `refresh_status()` re-renders the diff pane over `_show_message` whenever the file list is non-empty. 00089 ("TUI pull failure with warnings -> diff pane shows error and patch path") and 00090 ("a cancel shows `Pull cancelled; nothing changed`") assert that pane. Fix: add to both TUI tasks "when asserting the diff-pane text, mock `status()` to return no entries (pre-existing re-render overwrite, deferred in batch 202610121200)".
- [00090, 00091] A stale `New symbols:` lines that declare 00088's symbols as "created by prerequisite PRD 00088, must exist before this PRD starts". 00088 is done and those symbols resolve in the repo. Harmless to the gate; drop for accuracy.
- [00090, 00091] G changelog: the docs tasks name `docs/source/tools/dot.rst` and `README.md` but not `CHANGELOG.md`. The changelog rule is blocking per `feat` commit (00088 satisfied it through the commit hook without a PRD task; 00089 names it explicitly). Fix: add a `CHANGELOG.md` `[Unreleased]` `**dot**:` Added entry to each docs task's acceptance.
- [00089] A two `(guess)` markers remain (`#### Feature: Messages (guess)`, `DotGitService.pull(...)` "(guess)"). Within create-prd's 2-marker allowance, but this gate is the last attended stop: confirm the values and remove the markers (see Questions).
- [00089, 00090, 00091] A feature blocks missing Description/Inputs/Outputs fields: 00089 "Messages (guess)" and "Recovery output (M5)"; 00090 "Apply rescue" and "`dot pull` with rescue"; 00091 both Self-heal features. Template drift only; plan-tasks parses `#### Feature:` headings, not the fields. No edit.
- [00089, 00090] F sizing: 261 and 259 lines, over create-prd's ~200 split hint, but both are dense contracts in one subsystem with coupled phases (00090 ships localize and rescue together by discovery decision). PRD prose adds ~4K tokens per task against the 150K budget. No split.
- [00090] G half-migration: adds `DotGitService.untrack(path)` (`cfg rm -r --cached --quiet`) beside the existing `rm(path)` (`cfg rm --cached` plus git-secret handling). Acceptable: localize refuses secrets first and needs `-r`. No edit; candidate for a later cleanup.
- [00089] A/E `catchup: force` suggested (see Frontmatter tuning).

### Questions

- [00089] Messages (guess), lines 79-86, and the `DotGitService.pull(passphrase=None, *, exclude=(), fetched=False)` signature, line 135: confirm as written, or supply other values, then remove the markers.

## Reshapes

- Renumber 00089 -> 00092. Reason: it depends on 00090 (`fetch`, `has_upstream`, `CommandPull` rescue flow, `CommandLocalize`, two-host test helpers). 00091 is independent of 00090, so order 00090, 00091, 00092 runs clean and keeps the dot PRDs adjacent (warm batch cache). The intake dir `intake/new/00089-dot-pull-divergence-report/` keeps its name; the PRD's Source line cites that path explicitly.

## Gaps

- No PRD reconciles the two untrack paths (`rm` vs new `untrack`). Fine for now.
- `dot unlocalize` (discovery nice-to-have) has no PRD; not a must-have gap.
- Glean `link_roots` config (00088 discovery M13) is manual by design (config outside gems); recorded in 00088 and 00090 Risks.
- The pre-existing TUI diff-pane overwrite bug (deferred by 00088's run) has no PRD and will keep forcing empty-file-list mocks in every TUI message test. Recommend a small follow-up PRD or an entry in the next `/assess-evolution`.
- Traceability: 00088 discovery M8-M12 land in 00090/00091 (M13 manual); 00089 discovery M1-M9 and all its success criteria map to 00089 features and two-host cases (1)-(6). No dropped must-have.

## End state after this batch

dot gains the full host-links lifecycle: manifest + materialize + hooks (00088, done), localize + pull rescue with collision choices in CLI and TUI (00090), hooksPath self-heal + `dot setup` for fresh hosts (00091), and pull divergence patches with pending-patch status (00092). Every action goes through a command class shared by CLI and TUI, so the one-implementation invariant holds. Left half-finished: the TUI message-overwrite bug stays deferred; localizing `~/.config/gita/repos.csv` and adding glean `link_roots` are manual steps after 00090; Windows junction settling in glean stays out of scope.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00092 (ex-00089) | `catchup: force` | the batch catchup cache is at `cbde51d2`, before 00088's code; by the time 00092 runs, 00088 + 00090 + 00091 have reshaped `git/service.py`, `commands/pull`, `commands/status` and the TUI it edits |
| 00090 | none | `opus` + `design: run` fit the destructive blast radius |
| 00091 | none | `sonnet` fits: exact commands and messages, premise pins the three repointed tests |

## Decisions applied

(filled during the apply pass)

# Backlog review - buvis-gems - 2026-10-12

Verdict: GO (all Blocking findings resolved by applied edits; see Decisions applied)

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00090 | dot-host-links-localize-pull-rescue-v1 | standard | 262 | dot: hostlinks, commands/localize, commands/pull, git/service, tui, cli; pybase console `choose` | 00088 (done) | READY |
| 00091 | dot-host-links-setup-v1 | standard | 190 | dot: git/service, commands/setup, status, settings, cli | 00088 (done) | READY |
| 00094 | updater-installer-index-parity-v1 | standard | 202 | pybase updater: index (new), state, checker, executor, `__init__` | none | READY |
| 00095 | dot-pull-divergence-report-v1 (was 00089) | standard | 262 | dot: git/service, commands/pull, commands/status, tui, new divergence.py | 00088 (done), 00090 | READY |

Mechanical checks (step 1):

- `check_links.py`: 0 findings under `prds/backlog/` or `prds/wip/`. The script exits 1 on out-of-scope files only (`research/00062`, old reviews, specs, and `designs/00088-...-design.md:3`, which cites the PRD at its old `prds/wip/` path).
- `ground_prd.py` on `backlog/` (four PRDs): 316 rows, 168 `ok`, 148 `declared-new`, 0 `missing` / `unresolved` / `unverified`. Caveat: 00095 passes partly by declaring 00090's symbols (`fetch`, `has_upstream`, `plan_rescue`, `CommandLocalize`, `RescuePlan`) as its own new symbols, so the pass is vacuous until 00090 lands; the renumber makes that order real.
- Hygiene: only `NNNNN-{slug}-v1.md` files in `backlog/`; numbers unique across backlog/wip/done/hold and the intake dirs (`intake/new/00088`, `00089`, `00092`, `00093` are discovery sources; no `discovery/` dir in this repo); `wip/` and `hold/` empty. `wip/` had vanished mid-review (empty dir, untracked) and was recreated so Phase 0's backlog-to-wip `mv` cannot rename a PRD to a file called `wip`.
- Batch state: `autopilot/state.json` batch 202610121200 is live (`next_phase: build`, 00088 completed, no pinned queue). Phase 0 picks the lowest backlog number per session, so the renumber takes effect at the next selection (00090). `session-brief.md` / `contract-card.md` still say "next: selects 00089"; both are regenerated per session.
- Concurrency: another session wrote during this review. It committed PRD 00094 (`3b746995`), intake dirs 00092 and 00093, a dot docs change (`a8092ccd`) and an early copy of this report (`af7e6a33`). The first renumber (00089 -> 00092) collided with intake 00092 and was redone as 00089 -> 00095, the create-prd re-scan rule in practice.
- Law loaded from `~/.agents/skills/create-prd/SKILL.md` + `assets/standard.md`; budget and tier rules from `autopilot` plugin 0.9.0 `plan-tasks` steps 4.5-4.7 (150K per-task threshold, `default_model` floor).

## Findings

### Blocking (both resolved, see Decisions applied)

- [00089 -> 00095] E collisions, order break: lines 9-11 say "Lands after 00088 and 00090: it reuses 00090's `fetch()`, `has_upstream()`, `CommandPull` rescue flow and two-host test setup", and the Phase 1 premise `rg -n "def fetch|def has_upstream" src/tools/dot/git/service.py` (expect 2) has 0 hits today. Autopilot drains ascending, so 00089 would be selected before 00090 -> fails as: stall (the premise check trips and the task stops), and case (5) of the two-host test cannot exist without 00090's `CommandLocalize`. Fix applied: renumber to 00095; order is now 00090, 00091, 00094, 00095 (00091 and 00094 are independent of 00090).
- [00089 -> 00095] D grounding, stale since 00088 landed: (a) Phase 2 task 2 premise `rg -n "def _mock_git_ops" tests/tools/dot` (expect 2): actual 3 (`test_tui_app.py:11`, `test_tui_host_links.py:14`, `test_tui_snapshots.py:52`) and the task says "if the count differs, stop and report" -> fails as: stall. (b) Module "dot commands and TUI" exported `StatusBar.update_info(info, error=None, pending=None)`; the live signature is `update_info(info, error=None, link_problems=0)` (`status_bar.py:26`, 00088) -> wrong-TDD lock-in against 00088's tests. (c) "`CommandStatus` stores `dotfiles_root`" was already true (`status.py:25`). Fix applied: `refresh_status` reads `pending_patch_warning(self._dotfiles_root) if self._dotfiles_root else None` (`MainScreen._dotfiles_root` exists since 00088, `main.py:117`), the mock-helper premise is gone, the signature keeps `link_problems=0`, the "stores" clause is gone.

### Non-blocking

- [00095, 00090] B/D TUI diff-pane assertions (applied): 00088's run deferred a pre-existing bug (`autopilot/deferred/202610121200-deferred.json`, `main.py:181`) where `refresh_status()` re-renders the diff pane over `_show_message` whenever the file list is non-empty. Both TUI tasks now say to mock `status()` with no entries when asserting the pane text.
- [00090, 00091] G changelog (applied): docs tasks now name `CHANGELOG.md` `[Unreleased]` beside `dot.rst` and `README.md`; the changelog rule is blocking per `feat` commit and 00095 already named it.
- [00095] A/E `catchup: force` (applied): the batch catchup cache is at `cbde51d2`, before 00088's code; by the time 00095 runs, 00088 + 00090 + 00091 have reshaped the files it edits.
- [00095] A `(guess)` markers (applied): the seven message strings and `DotGitService.pull(passphrase=None, *, exclude=(), fetched=False)` confirmed as written; markers removed.
- [00094] B premise without a pinned count (applied, rule-mandated by create-prd's premise rule): executor premise now reads `rg -c "def test_" tests/lib/pybase/updater/test_executor.py` (expect 20).
- [00094] C Outputs vs Behavior (applied): lookup Outputs said `None` when the lookup fails while Behavior falls back to PyPI first; now `None` only when both fail.
- [00094] A `(guess)` cwd = state dir (applied): confirmed as a decision, marker removed.
- [00094] G docs (applied): README line 42 says `--update` "force-checks PyPI"; a docs task now keeps that paragraph true after the installer-index change.
- [00090, 00091] A stale `New symbols:` lines declaring 00088's symbols as "created by prerequisite PRD 00088, must exist before this PRD starts" (declined by the user: cosmetic, the gate resolves them either way).
- [00090, 00091, 00094, 00095] A feature blocks missing some Description/Inputs/Outputs fields (00095 "Messages", "Recovery output (M5)"; 00090 "Apply rescue", "`dot pull` with rescue"; 00091 both Self-heal features). Template drift only; plan-tasks parses `#### Feature:` headings, not the fields. No edit.
- [00090, 00095] F sizing: 262 lines each, over create-prd's ~200 split hint, but dense contracts in one subsystem with coupled phases (00090 ships localize and rescue together by discovery decision). PRD prose adds ~4K tokens per task against the 150K budget. No split.
- [00090] G half-migration: adds `DotGitService.untrack(path)` (`cfg rm -r --cached --quiet`) beside `rm(path)` (`cfg rm --cached` plus git-secret handling). Acceptable: localize refuses secrets first and needs `-r`. No edit; candidate for a later cleanup.
- [00094] D unverifiable CLI claim: whether `mise latest pipx:buvis-gems` honors `minimum_release_age` could not be checked offline. The PRD's verification plus 24h back-off is the safety net either way (Risks, "Mismatched sources"). No edit.

### Questions

- None open. The 00095 message strings and pull signature were confirmed in the walkthrough.

## Reshapes

- Renumber 00089 -> 00095 (applied via `git mv`, first attempt 00092 collided with `intake/new/00092-sysup-expiry-tracking` created mid-review). Reason: it depends on 00090. The intake dir `intake/new/00089-dot-pull-divergence-report/` keeps its name; the PRD's Source line cites that path explicitly.

## Gaps

- No PRD reconciles the two untrack paths (`rm` vs new `untrack`). Fine for now.
- `dot unlocalize` (discovery nice-to-have) has no PRD; not a must-have gap.
- Glean `link_roots` config (00088 discovery M13) is manual by design (config outside gems); recorded in 00088 and 00090 Risks.
- The pre-existing TUI diff-pane overwrite bug (deferred by 00088's run) has no PRD and will keep forcing empty-file-list mocks in every TUI message test. Recommend a small follow-up PRD or an entry in the next `/assess-evolution`.
- 00094 has no discovery doc (create-prd allows skipping it); its must-haves come from the 2026-10-12 outage and are each pinned to a named regression test.
- Traceability: 00088 discovery M8-M12 land in 00090/00091 (M13 manual); 00089 discovery M1-M9 and all its success criteria map to 00095 features and two-host cases (1)-(6). No dropped must-have.

## End state after this batch

dot gains the full host-links lifecycle: manifest + materialize + hooks (00088, done), localize + pull rescue with collision choices in CLI and TUI (00090), hooksPath self-heal + `dot setup` for fresh hosts (00091), and pull divergence patches with pending-patch status (00095). Every action goes through a command class shared by CLI and TUI, so the one-implementation invariant holds. The updater (00094) stops trusting PyPI alone: it asks the installer's index, verifies an upgrade happened, backs off for 24h on a no-op, and `--update` reports installer lag honestly. Left half-finished: the TUI message-overwrite bug stays deferred; localizing `~/.config/gita/repos.csv` and adding glean `link_roots` are manual steps after 00090; Windows junction settling in glean stays out of scope; intake ideas 00092 (sysup expiry) and 00093 (dot add untracked) are not yet PRDs.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00095 (ex-00089) | `catchup: force` (applied) | batch catchup cache predates 00088's code; 00088 + 00090 + 00091 reshape `git/service.py`, `commands/pull`, `commands/status` and the TUI before 00095 runs |
| 00090 | none | `opus` + `design: run` fit the destructive blast radius |
| 00091 | none | `sonnet` fits: exact commands and messages, premise pins the three repointed tests |
| 00094 | none | `sonnet` + `design: skip` fit: every command, regex and message is given verbatim; catchup cache already includes the 0.14.1 updater fix |

## Decisions applied

1. Renumber 00089 -> 00095 (`git mv`; first try 00092 collided with a mid-review intake dir). Updated: 00090 Risks reference, capsule Active Work list. Status: applied.
2. 00095: pending warning via `MainScreen._dotfiles_root`, mock-helper premise dropped, `update_info(info, error=None, link_problems=0, pending=None)`, "stores dotfiles_root" clause dropped. Status: applied.
3. 00095: both `(guess)` markers removed; messages and pull signature confirmed. Status: applied.
4. 00095 and 00090: TUI tasks note the empty-file-list mock for diff-pane assertions. Status: applied.
5. 00090 and 00091: docs tasks include the `CHANGELOG.md` entry. Status: applied.
6. 00095: `catchup: force`. Status: applied.
7. 00090 and 00091: stale 00088 prerequisite symbol lines. Status: rejected by user (cosmetic).
8. 00094: executor premise pinned to 20 tests (rule-mandated). Status: applied.
9. 00094: lookup Outputs aligned with Behavior; cwd guess confirmed and marker removed; README docs task added. Status: applied.
10. `prds/wip/` recreated (empty, untracked). Status: applied.
11. Follow-up on the user's question: intake items 00088 and 00089 moved to `intake/processed/` per the layout rule (`structure-git-repo/references/layout.md:64-68`, "processed means a spec exists"); the four `Source:` lines (00088 done, 00090, 00091, 00095) repointed; stale `Status:` lines in both idea files updated. 00092 (sysup expiry) and 00093 (dot add untracked) stay in `new/`: idea only, open questions, no discovery or PRD yet. Gap: no skill or hook performs this move; `create-prd` still points at the legacy `discovery/` dir. Status: applied; skill fix queued for agent-skills.

Lens A re-run on the four touched PRDs after the apply pass: every `##`/`###` heading of `standard.md` present in order; every task line carries `Acceptance:`; 0 `(guess)`/TBD/TODO markers; frontmatter fields all recognized with valid values; `ground_prd.py` 0 bad rows; `check_links.py` 0 in-scope findings.

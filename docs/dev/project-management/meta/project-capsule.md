# Project Capsule: buvis-gems

Generated: 2026-11-13 (catchup: feature/config-local-layer-braid, batch 202611131903)

## Key Invariants
- Commands return `CommandResult`; only `cli.py`/adapters render via `console`. No print/click.echo/logging.
- Persist with `pybase.filesystem.atomic_write`, never bare `write_text`.
- dot: one action, one implementation across CLI/TUI (`DotGitService` is the seam, PRD 00053). TUI must call the same command classes as CLI.
- Lazy imports inside Click handlers.
- Every CLI change updates `docs/source/tools/<tool>.rst` and `README.md`.
- sysup: a string step or refresh command runs as `bash -eo pipefail -c <line>`; an argv list runs without a shell; either may be `{argv, env}` with `env` merged over the parent for that step only. Two expansion layers: the loader expands `${VAR}` first, bash second; `$${...}` passes through to bash. Sudo priming triggers on `sudo` as a word anywhere in the line, not only argv[0].
- sysup spawn seam is `_run` in `runner.py` (tests mock `sysup.runner._run`, never `subprocess.run`). Only a captured step with a timeout runs in its own process group: the timeout SIGKILLs the group and Ctrl-C forwards SIGINT to it, because a background group never sees the terminal's SIGINT and cannot read the tty (a prompt stops it until the timeout). Everything else stays in the terminal's group: interactive steps must read the tty for sudo and brew prompts, and a step without a timeout has nothing to kill. Residuals (#252): an interactive step's timeout kills bash alone, and a command running as root through sudo cannot be signaled by sysup at all (`sudo -n kill -- -<pgid>` off the primed ticket is the upgrade path, `ponytail:` note in `_run`). `start_new_session` is wrong here: it drops the controlling tty and sudo's tty-keyed ticket. No bundled entry sets `timeout`.
- Never `git init`/`git clone` inside the checkout under the Seatbelt profile: `.git/hooks/` creation is denied, the half-made repo falls through to gems' own `.git`, and commits land in gems as `Test User` (dot's fixture identity). `dev/local/` is gitignored since d314a3bf for the same incident.

## Architecture Decisions
- Single PyPI package `buvis-gems`; tools are top-level packages in the wheel.
- dot works against a bare dotfiles repo (`cfg` wrapper, work-tree `$HOME`); `dotfiles_root` is resolved in `cli.py` (`DOTFILES_ROOT` env).
- sysup steps are shell lines (v0.16.0, PR #253). This reverses decision #2 of PRD 00079 (argv lists, no shell): the user config had already grown `sh -ec` script steps, so "no shell" had only moved the shell into the data. `-e` stops a multi-command step at its first failure; `pipefail` fails the step on any failing pipe member.
- The bundled `brew` step runs interactively with `--no-ask` and `HOMEBREW_NO_UPGRADE_AUTO_UPDATES_CASKS=1`: interactive so cask sudo prompts are visible (0.15.2), `--no-ask` so the proceed prompt cannot stall the run (0.15.3), the env var so self-updating casks are left alone (0.16.0). Three patch releases in two days came from that one step; change it with all three constraints in mind.
- postup ships its committed SvelteKit build; the hatch hook rebuilds it only for release wheels (41bcbcbb). A Renovate bump of the postup frontend lock merges green with stale assets until someone runs `npm ci` + `npm run build` and commits `chore(postup): rebuild web frontend assets`.

## Component Boundaries
- `src/tools/dot/`: `cli.py` -> `commands/<name>/` -> `git/service.py` (`DotGitService`); TUI (`tui/app.py`, `tui/screens/main.py`, `tui/widgets/status_bar.py`) drives the same commands.
- dot's host-filter surface lives in `src/tools/dot/git/filter_driver.py` as `FilterDriverMixin` (split out of `service.py` at 861 lines, over the 800 max); `_literal` moved there and `service.py` imports it from there.
- sysup capabilities yield `StepResult`; config validates their `inputs` against `with:` and the runner owns dry-run, error conversion, command stamping, and run-log markers. Registering a capability therefore exposes it through the existing shared runner without another interface implementation.
- sysup step shape normalization (string/list/object -> argv + `label`) is a config-layer concern (`StepSpec`); `runner.py` only sees resolved argv, the child env and the label used for dry-run and the run log. The timeout ceiling above lives in the runner because that is where the spawn seam is.

## Active Work

### Batch 202611131903 (feature/config-local-layer-braid worktree, PR #275 open)
- [ ] 00136-sysup-plan-config-errors-raw-v1.md (lane full, design skip): sysup `load_config` validates the raw merged layers, so shared keys (`debug`, other tools' sections) fail `extra="forbid"`, list directives on unknown-to-merge keys traceback, and `ValidationError` renders raw. `backup/config.py` already projects onto `_BACKUP_TOP_LEVEL_KEYS`, rejects unknown keys only in `buvis-backup*.yaml`, and wraps merge errors in `FatalError` — it is the template. backup still interpolates raw `ValidationError` text (pydantic URL) into its FatalError.
- Remaining backlog: 00137-00140 (agoge deferred findings from batch 202611101200).

### Batch 202611101200 (feat/config-local-layer-braid worktree, `~/git/src/worktrees/gems/feat-config-local-layer-braid`)
- [x] 00122-config-machine-local-layer-v1.md (1 cycle, fast-track lane): dropped `local.yaml` sibling twins for a `~/.local/.config/buvis` machine-local config layer, per `~/.claude/AGENTS.md`'s "machine-local config never sits loose beside tracked config" rule.
- [x] 00123-braid-config-in-buvis-yaml-v1.md (1 cycle, lane: full): braid drops `~/.config/braid/sources.d` and `--config-root`/`BUVIS_BRAID_CONFIG_ROOT` for `sources`/`policies` lists in `buvis-braid.yaml`, read through the shared loader so 00122's machine-local layer composes them via `sources+:`. Depends on 00122 (done). Source: gems#272; sibling issue #273 (config loader machine-local read path) is a separate PRD, not in scope here. Review cycle 1 converged: 12 autonomous-decision findings all single-voice [1/4], discarded to the audit ledger, no CRITICAL/HIGH.

Observations: batch 202611101200 drained (both PRDs done); `docs/dev/project-management/prds/backlog/` was missing in this worktree (recreated via mkdir -p — the Phase 0 lifecycle-dir step should have created it).

### feature/muc-tidy-reporting
- Implemented intake `00121-muc-tidy-report-through-console/idea.md`: all five helpers return actions and recoverable warnings through `CommandResult`, aggregated by `DirTree` and `CommandTidy`. No logging remains in muc.
- Decisions: show every action, continue after individual failures, keep warnings at exit status 0. CLI selects literal console rendering while programmatic results retain plain text. Case-only extension changes compare names rather than Windows case-insensitive Path equality.
- Created from master at `7cae3a37` on 2026-11-10 00:12 CET; no PR or wip PRD. Implementation verified with the muc suite, ruff and mypy.
- Independent native Claude Sonnet 5.5 review at high effort found no blockers; follow-up fixes passed re-review with no remaining actionable findings. Evidence and deferred pre-existing risks: `reviews/muc-tidy-reporting-independent-review.md`.
- The older BIM progress notes below are historical: PRDs 00118–00120 landed in #269, the branch's starting commit.

### feature/improve-bim-from-skill-experience
- PRD 00118 has committed local-time identity, collision-safe allocation, and shared scripted command/body/source/dry-run behavior. Original tasks 1–2 are complete; task 3 has passing tests but lacks Pat review because its assembled review exceeded the 50 KB dispatch cap. CLI scripting flags, failure exits and documentation remain unfinished.
- Replan attempt 1 has a hard 75,000-token per-task budget. A file-boundary split still leaves the required CHANGELOG.md task at 81,132 tokens under the installed full-file estimator (80,696 before any requirement or plan text). The canonical oversized_task stall parks 00118; see autopilot/reports/00118-replan-1-budget.md and its JSON evidence. No implementation or completion review ran in this replan session.
- Preserve d8692476 as the original work_start_sha in the archived state and retain all contributing Sol/Astra metadata and raw worker logs. The branch also contains large retained transcripts and PM evidence.
- Preserve Path return type, shared five-candidate allocation budget, no-write dry run, formatter injection across CLI/TUI/WebUI, and JSON payload exception to console output.
- PRDs 00119 and 00120 remain dependent follow-ons and must await completion reviews.

### Batch 202611042342 (feat/braid worktree, `~/git/src/worktrees/gems/braid`)
- [x] 00115-braid-port-skills-parity-v1.md (2 cycles): braid ported into `src/tools/braid/`; two deliberate parity breaks fixed in cycle 1 (Windows junction via `_winapi`, not cmd.exe; non-UTF-8 inputs exit 2). The cmd.exe junction injection still lives upstream in agent-skills braid.
- [x] 00116-braid-rules-kind-v1.md (2 cycles): rules as a second kind (`domain/rules.py`), generated single-file host instructions, `UNMANAGED` host links. Cycle-2 rework: Windows instruction-file ownership judged by pre-write identity, `sync_rules` emit taken positionally.
- The worktree's `wip/` also held a stale copy of 00117, which belonged to the master checkout's batch 202611040755 and was never selected there; the 2026-11-08 merge into master kept master's `done/` move.
- Pre-merge branch review (2026-11-08, `reviews/feat-braid-branch-review-1.md`): 4 single-voice Lows, no rework; full suite 6824 passed at b27b48b5.
- New tool gotcha: `src/tools/` now holds 17 tools (backup, klyreon, postup not in the AGENTS.md tree), so the README "15 -> 16" count in 00115 must be checked against the real README count.

### Batch 202611040755
- [x] 00117-backup-bundle-out-under-source-v1.md (2 cycles)

Observations: Batch drained; all four tasks completed, including the cycle-2 Tail sweep. Both provider rosters and the original and companion implementation audits passed the host evidence gate. Final isolated suite: 6654 passed, 16 skipped, 1 xfailed; backup ruff and mypy passed. Earlier host-dependent test isolation failures remain in the deferred ledger. Evidence: `autopilot/reports/202611040755-report.md` and `autopilot/reports/00117-tail-sweep-work.md`.

## Related context

2026-11-13: topic "config local layer braid / sysup crashes or dumps raw pydantic errors on valid-looking config". engram skipped per `autopilot catchup-probe` (skip list: engram); no query, no hits, no staleness stamp. Source evidence: `audit-results/agoge-2026-11-10-2.md` finding 8 and `agoge-2026-11-12.md`. Task restore: `no_tasks_dir`.

2026-11-10: topic `muc tidy reporting`. Repo indexing/query and review harvest could not resolve this unregistered worktree. Portfolio hit: `gems/src/tools/muc/cli.py:60-86` — 0.0164, the existing tidy renderer. Other returned hits were unrelated. Portfolio status reported stale/dead rows (exit 1), including code stale=34/dead=133; results are not a fresh repo index. Task restore returned `no_project_data`.

2026-11-09: engram review harvest, indexing and related queries skipped per catchup probe; engram unavailable/unregistered. Topic: "improve bim from skill experience — bim create: scripting contract for agents". No query or portfolio staleness stamp was obtained. Source rationale is the 2026-11-08 create-note comparison recorded in PRD 00118; no discovery document was created.

2026-11-05 (topic "braid" / "braid: add rules as a second composed kind"): engram skipped by `autopilot catchup-probe` (unregistered), no query ran, no hits. Source discovery: `~/.claude/docs/dev/project-management/discovery/00182-layer-agent-rules-across-hosts.md`.

2026-11-04 (topic "braid" / "braid: port the skill composer into gems at parity"): engram skipped by `autopilot catchup-probe`, so no query ran and no hits are recorded. Reference code lives at `~/git/src/github.com/buvis/agent-skills/src/agent_skills_braid/cli.py` and `tests/test_braid*.py`.

Previous (2026-10-29): No topic this session: catchup ran on master with no `prds/wip/` directory, so no engram query was made. Review harvest ran: 13 review files upserted, the rest (audits, task logs, backlog reviews, `docs/dev/tmp` scratch) rejected for missing or incomplete frontmatter, which is expected for those formats. `engram status --scope portfolio` (exit 1, 2026-10-29): memory 192/stale 24/dead 1; prd 11485/dead 3063; discovery 554/dead 50; transcripts 17713/dead 17604; code 62674/stale 69/dead 1466, skipped 5840; findings 49747; decision 29. The dead rows are the staleness stamp any later portfolio hit should be read against.

## GitHub State
- 2026-11-13: 2 open issues (#272 braid config, #273 loader machine-local read path, both addressed on this branch). Open PR #275 (this branch -> master), no reviews; its Test run was queued at catchup. Latest release `gems-v0.20.0` (2026-11-10); 8 master commits since (Renovate frontend bumps #276-#278, muc #274). Master Test green. Remote branches: renovate/patch-all-non-major-dependencies, renovate/lock-file-maintenance, claude/python-3.15-wheels.
- 2026-11-09: 0 open issues; 1 open PR, #267 (`renovate/jsdom-31.x`, jsdom 30.1.3 -> 31.0.0). All listed checks pass. It touches only postup frontend package manifests/lock, with no bim overlap.
- Latest GitHub release: `gems-v0.19.2` (2026-11-08); two master commits follow it.
- Current master `a087e05e`: latest Test and documentation deployment completed successfully (2026-11-09 catchup). Latest completed Test, 42519713815 at `4876cad1`, succeeded, as did `f64f21a4`.
- Most recent historical failure: run 42519342178 (`ad421654`), lint Type check. Fix `f64f21a4` records Linux mypy treating darwin-only `_libc` as undefined and failing to narrow `hasattr(os, "setxattr")`; selecting the backend by `sys.platform` fixed it. Retrieved error: `src/tools/muc/shared/dir_tree/merge_mac_metadata.py:97: error: Name "_libc" is not defined [name-defined]` (1 error, 570 source files checked). No failing runs exist for this feature branch.
- Remote branches seen: master, gh-pages, renovate/jsdom-31.x, renovate/lock-file-maintenance, claude/python-3.15-wheels. Local `agoge/authored-tests-2026-10-26` remains; cleanup eligibility was not established.

## Project Health
- Latest master CI is green; this feature branch has committed production changes but no completion review. This catchup ran no tests and implemented no code. PRDs 00119 and 00120 remain blocked on 00118's implementation and completion review.
- Current dependency PR has green checks. Preserve the existing postup committed-build constraint when assessing its lockfile update.
- Local tests historically need isolated Cargo/config/state directories and removal of `GIT_AUTHOR_*`/`GIT_COMMITTER_*` noise. Re-evaluate those environment workarounds against the active host before applying them; prior capsule counts are historical evidence, not a baseline for this branch.
- Capability gaps: engram skipped per probe; memory loader returned no files; task-session listing returned `no_tasks_dir`, so no tasks were restored. `TaskCreate`/`TaskUpdate` are not available in this host. No `agent_docs/`, project decisions/troubleshooting keepers, or global `~/.claude/decisions.md` were found.
- PRD 00118 has meaningful external behavior changes (local-time ids and nonzero failure exits); keep release notes and all-interface tests aligned. Muc console-output debt is already recorded in intake 00121, outside this batch.

## Project Memories
- Release: verify PyPI moved after every release (`release-publish-gotcha`).
- CI: three green/red traps (`gems-ci-green-traps`); run mypy locally after any lock refresh.
- Git: `~/.buvis` bare-repo empty-output traps; agoge probe spoofed `origin/master` once, so `git fetch` before trusting ahead/behind.
- Env: Seatbelt profile, not Claude's sandbox, decides writable paths (`local-test-env-traps`).
- Deps: bincode v3 dead, serde_yml 0.0.13 is a terminal shim, ruff pins must move together, frozendict rejected for config until requires-python reaches 3.15.

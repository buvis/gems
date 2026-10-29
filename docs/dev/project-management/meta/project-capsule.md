# Project Capsule: buvis-gems

Generated: 2026-10-29

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
- No active autopilot batch: `autopilot/state.json` is absent, `prds/wip/` and `prds/backlog/` do not exist, `hold/` is empty. Last batch 202610261200 (00108) drained; its one deferred VERIFY is resolved (210e674c) and its test follow-ups closed 2026-10-29: `test_moves_every_well_formed_receipt_in_place` covers every receipt shape, pinned or not, including the two `future = false` receipts 00105 used to skip.
- Last shipped work: sysup shell-line steps (PR #253, merged 2026-10-28), released as gems-v0.16.0 on 2026-10-29 (tag pushed, publish run in flight at catchup time).
- #252 (timeout orphaning from that PR's review) fixed 2026-10-29 for captured steps; the interactive residual is recorded in the invariants.
- Intake pending: `intake/new/00107-backup-multi-source-parallel/` (idea + discovery, no PRD yet).

### Batch 202610261200
- [x] `00108-sysup-uv-tool-python-upgrade-in-place-v1.md` (1 cycle)

Observations: Fast-track lane. `uv tool upgrade --python` now moves customized receipts in place. Eve's VERIFY items were confirmed against uv 0.13.5 and fixed in 210e674c (receipt restore before rollback; skip tools whose `pyvenv.cfg` minor is already the target).

### Batch 202610242315
- [x] `00105-sysup-uv-tool-python-pin-v1.md` (1 cycle)

Observations: New `UvToolPython` pins supported plain unpinned/older installs before uv upgrades (order35 before40); preserves newer pins, visibly skips customized/unreadable receipts, and reports rollback failures honestly. One HIGH deferred to batch-end: `engram`'s editable install stayed unpinned/red on this host (triage 00106, done).

## Related context
No topic this session: catchup ran on master with no `prds/wip/` directory, so no engram query was made. Review harvest ran: 13 review files upserted, the rest (audits, task logs, backlog reviews, `docs/dev/tmp` scratch) rejected for missing or incomplete frontmatter, which is expected for those formats. `engram status --scope portfolio` (exit 1, 2026-10-29): memory 192/stale 24/dead 1; prd 11485/dead 3063; discovery 554/dead 50; transcripts 17713/dead 17604; code 62674/stale 69/dead 1466, skipped 5840; findings 49747; decision 29. The dead rows are the staleness stamp any later portfolio hit should be read against.

## GitHub State
- 1 open issue: #252 (sysup timeout orphans multi-command shell steps; deferred from the #253 review, 2026-10-28).
- 2 open PRs, both Renovate majors from 2026-10-04 still reporting artifact-update failures: #220 SvelteKit v3, #219 adapter-static v4. #249/#248/#245/#231 merged since the previous capsule; the postup build was rebuilt after them (a47081b5). Branch `renovate/patch-all-non-major-dependencies` is a reused branch whose latest PR (#251) merged 2026-10-29; nothing open on it.
- master `ce65015c` == origin/master, tip author Tomáš Bouška, working tree clean, no stray `v*` tags (only `gems-v*`), verified after `git fetch` 2026-10-29.
- Latest release gems-v0.16.0 (2026-10-29). Zero unreleased commits. Publish run 40849147923 and master Test run 40849147682 were both mid-matrix at catchup: `lint` and all eight `lib` cells green, `tools` cells running, macOS cells queued. Last completed master Test (b73a8c5c, 2026-10-29 00:14) succeeded.
- The five red master Test runs of 2026-10-24..26 are all on autopilot telemetry commits and report `tools` as `abandoned`, not failed; the runs around them are green. Not a regression signal.

## Project Health
- CI green on the last completed master run; the v0.16.0 publish is not yet confirmed. Release rule: the tag is not the release, PyPI moving is. Check `gh run list --workflow publish.yml` or the PyPI JSON before treating 0.16.0 as shipped; an orphaned tag is recovered by `release patch`, never by re-tagging.
- A `lib` failure skips the `tools` matrix; a `queued` rollup usually already has `lint` and the ubuntu `lib` cells done (macOS runners are the bottleneck; the scoped PAT cannot cancel runs).
- Local tests: `uv sync` and every `uv run` need `CARGO_HOME=<scratchpad>/cargo-home` + `BUVIS_SKIP_FRONTEND=1`; the full suite's 3 env-noise failures isolate by dropping `GIT_AUTHOR_*`/`GIT_COMMITTER_*`, scratch `XDG_STATE_HOME`, and a scratch `BUVIS_CONFIG_DIR` holding `buvis-postup.local.yaml` with `roots: []`. #253 recorded 5706 passed / 0 failed / 2 skipped / 1 xfailed under that isolation.
- Debt: #252 and the 00108 test follow-ups are small and sysup-local; the two Svelte majors have sat 25 days blocked on Renovate's own artifact step and will need a manual lock update or a close.

## Project Memories
- Release: verify PyPI moved after every release (`release-publish-gotcha`).
- CI: three green/red traps (`gems-ci-green-traps`); run mypy locally after any lock refresh.
- Git: `~/.buvis` bare-repo empty-output traps; agoge probe spoofed `origin/master` once, so `git fetch` before trusting ahead/behind.
- Env: Seatbelt profile, not Claude's sandbox, decides writable paths (`local-test-env-traps`).
- Deps: bincode v3 dead, serde_yml 0.0.13 is a terminal shim, ruff pins must move together, frozendict rejected for config until requires-python reaches 3.15.

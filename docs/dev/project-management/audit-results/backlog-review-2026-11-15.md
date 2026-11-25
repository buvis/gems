# Backlog review - gems - 2026-11-15

Scope: Herdr PRDs 00156-00160 only, plus their dependencies. PRDs 00122, 00123
and Tiromex 00150-00155 were read for collisions only and are not judged here.

Verdict for the reviewed scope: GO (0 Blocking open; 3 Blocking fixed in place).
This is a specification verdict. Nothing is implemented, and no real
version-changing Herdr update has been exercised.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00156 | sysup Herdr clone audit | standard | 184 | sysup capabilities, default plan, docs | none | READY |
| 00157 | sysup Herdr observation bridge | standard | 174 | sysup herdr package, commands, packaging, docs | none | READY (after fixes) |
| 00158 | sysup Herdr snapshots and provenance | standard | 189 | sysup herdr store/lock, config, commands | 00157 | READY (after fixes) |
| 00159 | sysup observable Herdr updates | standard | 201 | sysup herdr update, capability, runner, default plan | 00157, 00158 | READY (after fixes) |
| 00160 | sysup reviewed Herdr clone ports | standard | 209 | sysup herdr port/apply, store, audit, commands | 00156, 00157, 00158 | READY (after fixes) |

Every dependency points at a lower number. 00160 does not need 00159.

## Findings

### Blocking (all fixed)

- [00157] B contracts: the Herdr mod API was named but not specified. The task
  line asked for a harness proving "real init argument order" without giving
  the imports, `checking()`, `cx.spawn`, the task context, the mod.json content,
  the command-prefix rule or the layout block. The test author sees the task
  text alone. The spike already lost one native run to a mock that repeated the
  mod's wrong argument order (`RESULTS.md`, request `c4eb22a2...`).
  -> fails as: wrong-TDD lock-in. Fix: pinned the exact 0.1.16 API in the Loaded
  bridge feature, the top-level `sysup.update-probe` member of shared.json, the
  layout block JSON, and pointed the task at the spike's `main.js` and
  `probe.mjs`.
- [00157] B executability: the wheel task required an always-on `uv build
  --wheel` test. `tests/tools/klyreon/assets/test_wheel_resolution.py` records
  that an in-process wheel build segfaults the CI interpreter at teardown and
  must be opt-in. -> fails as: rework thrash (acceptance cannot hold on CI).
  Fix: the task now follows that opt-in pattern (`BUVIS_WHEEL_BUILD_TESTS=1`,
  `BUVIS_SKIP_FRONTEND=1`, skip when the toolchain is absent).
- [00158, 00159, 00160] E order: nothing stopped a dependent PRD from being
  picked after its prerequisite stalled into `hold/`. 00158 would then "extend"
  a facade that does not exist and fake it. Tiromex 00151-00155 in this same
  backlog already guard this. -> fails as: order break. Fix: `eligibility:
  test -f docs/dev/project-management/prds/done/<prerequisite>.md` on all three.

### Non-blocking (all applied)

- [00157] B: the Node harness ran in no gate. `uv run pytest` and the CI tools
  matrix never call `node --test`. Fix: one pytest case runs the harness as a
  subprocess and skips only when node is absent.
- [00157] B unattended: "Recheck installed generated API at implementation"
  told a headless build to read the workstation's Herdr home, with no rule for
  a mismatch. Fix: build against the recorded 0.1.16 contract; do not read the
  live home during the build.
- [00157, 00158, 00159] C: a dependency-graph layer named a module the PRD does
  not define ("Packaging and adapters", "Baseline/reference ledger",
  "Configuration/documentation"). Fix: each layer names a defined module.
- [00158, 00159, 00160] E: each builds on interfaces a PRD earlier in the same
  batch creates, so a cached catchup would predate them. Fix: `catchup: force`.
- [00160] B: "three-way merge" named no implementation. Fix: a Risks line says
  to reuse `git merge-file` or an installed dependency and never hand-write a
  diff3. Reviewer decision, reversible; the design phase may still choose.
- [00156] B: the docs acceptance ended in "the rendered page contains those
  behaviors", which no command checks. Fix: added `rg` assertions.

### Questions

None. The settled choices in `decisions.md` were not reopened.

## Reshapes

None. 00160 is 209 lines and 00159 is 201, at the ~200 line guide. Both stay
whole: one subsystem, three phases, five and four task lines, and each task
names one or two files. Splitting 00160 at prepare/apply would ship a
preparation command with no way to apply. Risk accepted: if plan-tasks expands
00160 past 15 tasks it stalls to `hold/` and the split happens then.

## Gaps

- No slice exercises a real version-changing update. 00159 covers it with
  fake-process state-machine tests only; the first live opt-in run is the
  proof. This is stated in 00159's Risks and stays outside the batch.
- `sysup herdr` grows to about a dozen operations behind one `CommandHerdr`
  facade and one `cli.py` across four PRDs. The design phase of 00158 and
  00160 should split the module before it passes the 800-line limit.
- 00159 changes how the runner hands configuration to a capability. The
  mechanism is left to its design phase; `tests/tools/sysup/test_runner.py`
  is not in its tree, so new runner assertions belong in
  `tests/tools/sysup/test_herdr_update_integration.py`.

## End state after this batch

sysup gains a read-only clone audit in the default macOS plan, an explicitly
installed observation bridge, a bounded per-home snapshot store with a home
lock and an adoption ledger, a disabled-by-default update entry that reports
completion only from fresh observations, and an attended prepare/review/apply
workflow for personal clones. hmod keeps community mods. Default runs start no
agent, install no bridge, and restart nothing. Still missing afterwards: proof
against a real update, and any TUI/API/WebUI adapter (sysup has only a CLI; the
facade returns `CommandResult`, so the seam is ready).

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00158, 00159, 00160 | `catchup: force` (applied) | depend on code created earlier in the same batch |
| 00158, 00159, 00160 | `eligibility` (applied) | must wait for prerequisites in `done/` |
| 00159, 00160 | `rework_cap: 3` (not applied) | hard state-machine and recovery work; default 2 kept, raise only after a first stall |

## Gate honesty

- Lenses A-H ran inline on all five PRDs. Budget and tier rules were checked
  against create-prd's current text; `autopilot:plan-tasks` was not opened.
- `ground_prd.py`: 0 blocking, 0 unverified, 11 declared-new, run on the five
  files. It exits 2 when handed `prds/wip` because that directory is absent.
- `check_links.py`: no dangling citation in 00156-00160 before the edits. The
  new `eligibility` lines now report five forward references to `prds/done/`
  files. They are lifecycle outputs, the same shape as Tiromex 00151-00155,
  and are waived here. The checker also reports 12 unclosed-fence scan errors
  in `autopilot/reports/`, outside this scope and untouched.
- Grounding verified with `rg` and reads: `herdr-mods` at order 78, the
  `warned` and `unknown` statuses, attention folding, dry-run skipping the
  capability, `extra="forbid"` on `SysupConfig`, the XDG state root, existing
  `fcntl.flock` use, CI running ubuntu and macOS only, and node 26.13 present.
- Not verified: Herdr's live API beyond what the spike recorded, and whether
  the unattended sandbox can build a wheel (the opt-in test skips if not).
- The branch base was verified: `feature/merge-klyreon-to-bim` sits five
  docs commits on `origin/master` at `18429bfe`.

## Decisions applied

All findings above were adjudicated by the reviewer under standing
authorization; no interactive walkthrough ran. Edits touched only
`prds/backlog/00156` through `00160`. Lens A was re-run on the touched files:
headings, order, `Acceptance:` clauses and frontmatter keys still conform.

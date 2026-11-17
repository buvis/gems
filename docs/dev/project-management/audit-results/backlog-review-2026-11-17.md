# Backlog review - gems - 2026-11-17

Branch `feature/bim-utc-ids` at `254d663a` (one docs commit on `origin/master`).

Verdict: NO-GO for a blind drain (2 Blocking open). PRDs 00156 to 00162 are
READY after the fixes below. PRDs 00122 and 00123 are HOLD: they are already
built on the branch `feature/config-local-layer-braid`, which is not merged.
The loop selects the lowest number first, so a drain from this branch starts
with 00122 and builds it a second time.

This is a specification verdict. No test, build or Herdr command ran.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00122 | config machine-local layer | standard | 196 | pybase configuration, sysup text, docs | none | HOLD (done on unmerged branch) |
| 00123 | braid config in buvis-braid.yaml | standard | 191 | braid, docs | 00122 | HOLD (done on unmerged branch) |
| 00156 | sysup Herdr clone audit | standard | 189 | sysup capabilities, default plan, docs | none | READY (after fixes) |
| 00157 | sysup Herdr observation bridge | standard | 187 | sysup herdr package, commands, docs | none | READY (after fixes) |
| 00158 | sysup Herdr snapshots | standard | 199 | sysup herdr store/lock, config | 00157 | READY (after fixes) |
| 00159 | sysup observable Herdr updates | standard | 211 | sysup herdr update, runner, default plan | 00157, 00158 | READY (after fixes) |
| 00160 | sysup reviewed Herdr clone ports | standard | 229 | sysup herdr port/apply, store, audit | 00156, 00157, 00158 | READY (after fixes) |
| 00161 | bim UTC ids | standard | 171 | zettel lib, Rust core, bim docs | none | READY (after rewrite) |
| 00162 | bim id migration script | standard | 136 | spikes tree only | none in code; run after 00161 ships | READY (after rewrite) |

Every dependency points at a lower number.

## Findings

### Blocking, open

- [00122, 00123] D already implemented: on `feature/config-local-layer-braid`
  both files are in `prds/done/` (commits `1bc40806`, `f23a6c81`, `2fcaf2a9`).
  That branch is 137 commits ahead of master. Here the files are still in
  `backlog/`. -> fails as: selection break. `autopilot select` takes 00122
  first and the loop builds a second, different copy of code that must later
  merge with the first. Fix: see "Actions to reach GO". The files were not
  moved to `hold/`: the other branch renames them to `done/`, and a second
  rename here gives a rename/rename conflict at merge.
- [00161 against the unmerged branch] E contradiction: that branch adds the
  parity test `test_id_cut_from_the_file_creation_time_is_local_wall_clock`
  and makes `date_from_filesystem` local so that ids are local time. 00161
  makes ids UTC. The branch also edits `enrichment.rs`, the parity test file
  and `src/tools/bim/SKILL.md`, which 00161 edits. -> fails as: goal reversal
  across branches (the second merge breaks the first). Fix applied in 00161:
  the Rust task tells the implementer to change that test when it exists.
  The clean order is still: merge the config branch first.

### Blocking, fixed in place

- [inventory] hygiene: `discovery/00161-engram-port-plan.md` and PRD 00161
  shared a sequence number. Fix: `git mv` to `discovery/00163-engram-port-plan.md`
  (no file cited the old name; checked this repo, the master checkout, buvis/docs,
  `~/.claude/docs`, and project memory).
- [00161] ground_prd: `id_naive_timezone` unresolved (2 rows). It was a new
  `BimSettings` field with no Module block, no reader and no test.
  `set_default_id(zettel_data)` is called through the consistency service with
  no path for a setting. -> wrong-TDD lock-in. Fix: setting removed, see next row.
- [00161] D parity: "Naive dates do not occur on the Rust side" is false.
  `src/rust/src/types.rs:103-107` reads a naive frontmatter date and labels it
  UTC. Production reads go through Rust (`from_rust=True`). A Prague rule in
  Python alone gives ids 1 to 2 hours apart from Rust, and Rust has no
  `chrono-tz`. -> wrong-TDD lock-in (the parity exit criterion cannot hold).
  Fix (reviewer decision): a naive date is read as UTC in both paths, digits
  unchanged, which is today's behavior. PRD 00162 resolves old naive dates.
- [00161] B/C existing tests: the PRD said "additive tests" but 14 existing
  tests pin the old rules: `test_sets_id_from_dates_own_wall_clock`, the two
  `test_*_filename_is_local_wall_clock`, `test_raises_file_exists`, all five
  `TestCollisionBudget` tests, the parity test
  `test_default_id_follows_the_dates_own_offset_in_both_paths`, the assertion
  in `tests/tools/bim/test_create_note_vault.py:35`, and three Rust unit
  tests. -> rework thrash (the gate fails and nobody is told which tests to
  change). Fix: each task names the tests it replaces, with a premise.
- [00161] D wrong path: `tests/tools/bim/commands/doc/shared/test_naming.py`
  does not exist (real file: `tests/tools/bim/doc/test_naming.py`). Fix: the
  doc-ingest feature was removed, see Non-blocking.
- [00161] C/G docs: `README.md:181` and `docs/source/tools/bim.rst:249-251`
  state the local-time rule and the "waits for the next free id" behavior;
  the PRD named only SKILL.md. -> rework thrash at review. Fix: both files
  are in the tree and the Phase 2 task, with `rg` acceptance.
- [00162] D scope: `bim doc` zettels live under `notes/documents/`, have no
  `date`, already have UTC or `<doc date>000000` ids, and their file name is
  tied to a PDF and the doc state database. The text would have given them a
  `date`, moved their id by the Prague offset and renamed them away from
  their PDF. -> wrong-TDD lock-in on a destructive tool. Fix: `type: document`
  files are never renamed or re-identified.
- [00162] B contract: "rename each file" was undefined for notes whose file
  name is not the id (`contact/<slug>.md`, `book/<slug>.md`, hub and toc
  notes) and for `.md` files with no id (daily notes, boards). A literal
  build renames `contact/ada-lovelace.md` to `<id>.md` and breaks its links.
  Fix: rename only when the stem starts with the old id; a file with no id
  line is not a note.
- [00162] C contradiction: the final scan "for every old id" (Risks only, no
  task) would fail on ids in code fences, in `![..](<id>.svg)` links and in
  the project `resources` link, which the same PRD says not to touch. Fix:
  the scan is now part of Apply, limited to reference forms, with a test.
- [00162] C undo: the map held one hash (after the change), written before
  the change, and undo skipped every file whose hash differed. After a
  stopped apply, unchanged files look "changed since". Fix: before and after
  hashes, an explicit three-way rule, and the test
  `stopped_apply_then_undo_restores_bytes`.
- [00157] D pinned test: `tests/tools/sysup/test_sysup_cli.py:29` asserts
  `set(cli.commands) == {"refresh", "status"}`. Adding the `herdr` group
  fails it, and the file was not in the tree. -> stall on the file allowlist.
  Fix: file added to the tree and the Phase 1 task.
- [00157] B contract: the `updates()` field names were not recorded in the
  repo; the spike sample holds only 3 of them. Fix: the 0.1.16 type from the
  installed `herdr.d.ts` is now in the PRD (it matches the PRD's field list;
  the release notes member is `notes`).
- [00157] B acceptance: "obsolete-instance cancellation" asked the harness to
  prove a Herdr behavior the spike never recorded (`notify()` is a no-op in
  the spike mock). Fix: acceptance reduced to what the spike proved.
- [00160] B contract: "documented clone transformations" pointed at one prose
  sentence. Fix: the exact rules from upstream `src/mods.rs` at the pinned
  commit are in the PRD (three asset-prefix replacements, twelve `mod:`
  patterns, UTF-8 files only, pretty-printed mod.json with `cloned_from`).
- [00160] B contract: "refuse community-owned destinations" had no detection
  rule. Fix: eligible only when absent from installed.json, with a valid
  `cloned_from` and an accepted baseline; never read hmod records.

### Non-blocking, applied

- [00161] frontmatter: `default_model: sonnet` with the rationale "additive
  tests" did not hold (Rust edits carry no exact text, parity is an
  equivalence obligation, tests are rewritten). Now `opus`.
- [00161] scope: the feature "Doc ingest timestamps tolerate suffixes" was
  removed. `_increment_zk_seconds` only receives `_zk_timestamp` output and
  its own output, and doc files are not named `<id>.md`, so it never sees
  seconds 60 to 99. A Risks line records this.
- [00161] D: chrono accepts second `60` as a leap second, so the Rust parser
  must clamp before parsing; `CACHE_VERSION` in `scanner.rs` must go up;
  `MAX_ID_ATTEMPTS` and `import time` go; a lost `O_EXCL` race takes the next
  suffix; `set_default_id` in Rust is internal, not an export.
- [00161] C: slot count wording ("Collision 100", "the 41st raises") made one
  consistent rule; "three test files" is five; test names are `test_<name>`;
  the dependency graph named `SKILL.md`, which was no module (now `docs`);
  `rg -c` prints nothing on zero matches, so those acceptances changed.
- [00161] A: the `(guess)` marker on "seconds 60 to 99 map to 59" was removed
  and the rule kept as written.
- [00162] B tests: the script directory is not on `sys.path` under
  `--import-mode=importlib`, so the test loads the script by file path; the
  help test runs `sys.executable`, not a nested `uv run`; the map directory
  is a parameter so no test writes to the real home.
- [00162] D bytes: `atomic_write_text` translates newlines; the script now
  reads and writes bytes with `atomic_write_bytes`.
- [00162] B contract: date-only and unparseable dates, invalid old ids and
  the spring DST gap now have a rule and a test each; the reference regex has
  a digit boundary and accepts a folder in the link path; 12-digit ids are
  named.
- [00162] A: phase headings renamed to the template's wording; the
  dependency graph layer now names a defined module.
- [00162] Risks: stale `~/.cache/buvis/zettel_cache.bin`, archived notes,
  notes with a wrong offset from past bim saves.
- [00156] message carries the item path (the label is not shown when a
  message is set); community mods are audited like other nonshipped mods; a
  commit-hash version is a mismatch; tests control `HERDR_APP_HOME`; the
  exact darwin plan list gains `herdr-clones`.
- [00157] re-send the same nonce on "unknown command" until the deadline (the
  spike client does this; one dispatch reports false absence after a start);
  no directory helper exists in the library; keep the spike directory; CI
  tools job has no node; mod.json compared as JSON.
- [00158] home layout stated (it was defined only in 00156); 0600 and
  streaming need a store-local publish, not `atomic_write_bytes`; the config
  model and the `default.yaml` key land in one commit because `SysupConfig`
  forbids unknown keys; `fcntl.flock` named; docs must not name a
  machine-local file and must rename the `herdr:` example in sysup.rst.
- [00159] `timeout_seconds` is a `with:` input; an invalid policy gives one
  failed result; every outcome now maps to a status; existing capabilities
  keep their kwargs (`test_use_passes_with_inputs`); `sysup --dry-run herdr
  update` must not mutate (the group flag does not reach subcommands today).
- [00160] layout validation limited to what is known; durable-write helper
  local to sysup (the library helper does not fsync the directory); audit
  needs no config context; staging and backup location named; `mod.json`
  compared structurally like layouts; `git merge-file -p --diff3` only.

### Rejected

- [00158] "trailing prose on a `New symbols:` line poisons the gate":
  `ground_prd.py` ran today and reports those rows as declared-new.
- [00122, 00123] 15 text findings from the grounding pass (Rich line wrap in
  an assertion, self-contradicting `rg` gates, a Phase 0 that leaves mypy
  red, a README citation off by six lines, and others). Not applied: the
  work is done on the other branch and these backlog copies are stale.

### Questions

None open. The reviewer decided each point under standing authorization;
"Decisions applied" lists the ones the owner may want to change.

## Reshapes

None applied. 00160 (229 lines) and 00159 (211) are over the 200-line guide
after the fixes. Both stay whole: one subsystem, three phases, five and four
task lines; the added lines are contracts, not prose. If plan-tasks expands
00160 past 15 tasks, it stalls to `hold/` and the split happens then.

## Gaps

- klyreon `spec/validator.py:137` enforces id == `created` digits and
  `bim import` bumps a colliding id as an integer. 00161 leaves both alone.
  When klyreon merges into bim (branch `feature/merge-klyreon-to-bim`), check
  them against UTC ids and the 60 to 99 suffix.
- Only `sysup herdr update` gets a dry-run rule. `sysup --dry-run herdr bridge
  install`, `snapshot`, `adopt` and `port apply` still ignore the group flag,
  like `refresh` does today.
- No slice exercises a real version-changing Herdr update (carried from the
  2026-11-15 review).
- 00162 cannot tell a note that bim once saved with a wrong offset from a
  correct pre-00118 note; the dry-run count is the only signal.
- The backlog copy of 00122 says "no warning for a twin"; the branch later
  added a warning (its PRD 00126). The copy is history, not a spec.

## End state after this batch

With 00156 to 00162 done: bim writes UTC ids in Python and Rust with a
41-slot collision pool and no sleep, and the docs say so. A tested one-off
script exists for the owner to migrate one vault by hand. sysup has the
Herdr audit, bridge, store, opt-in updates and attended ports of the
2026-11-15 review. Still open afterwards: the vault itself is not migrated
(owner action), ids are mixed until then, and the config branch must be
reconciled with UTC ids if it merges after 00161.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00161 | `default_model: opus` (applied) | equivalence obligation and rewritten tests |
| 00161, 00162 | `catchup: force` (not applied) | add it only if they run in one batch after other PRDs on this branch |
| 00159, 00160 | `rework_cap: 3` (not applied) | carried; raise after a first stall |

## Actions to reach GO

Three real options. Option 1 is recommended.

1. **Merge the config branch first.** Merge `feature/config-local-layer-braid`
   into master, merge master into this branch, then drain. Good: 00122 and
   00123 leave the backlog with no edit here, and 00161 sees the local-time
   parity test and rewrites it. Bad: this branch waits until that branch is
   ready. Ugly: none found; the code needs this order anyway.
2. **Run by name, attended.** `/autopilot:run-autopilot 00161-bim-utc-ids-v1.md`,
   then 00162, and stop. Good: no wait. Bad: never start the `autoclaude` loop
   here, because the next pick is 00122. Ugly: the conflict with the config
   branch (parity test, `enrichment.rs`, SKILL.md) moves to merge time and is
   solved by hand.
3. **Park 00122 and 00123 in `hold/` on this branch.** Good: a blind drain is
   safe here. Bad: a rename/rename conflict when the config branch merges, and
   the five Herdr PRDs still run before 00161 on a bim branch. Ugly: lifecycle
   state differs between branches.

## Gate honesty

- Lenses A to C and E to H ran inline on all nine PRDs. Lens D ran as nine
  parallel subagents, one per PRD.
- Verified by the reviewer against the code: `types.rs:94-125`, every test
  name now in 00161, `README.md:181`, `bim.rst:249-251`, `naming.py:95-134`,
  `import_helpers.py:29-34`, `type: document` in `zettel_writer.py:91`,
  `test_sysup_cli.py:29`, `test_runner.py:188-196`, `sysup.rst:130`, the
  `updates()` type in the installed `herdr.d.ts`, the done state of 00122 and
  00123 on the other branch, and that branch's diff to `enrichment.rs` and
  the parity test.
- Taken from subagent reports with file and line evidence, not re-read: the
  Rust cache contents behind the `CACHE_VERSION` bump, the pytest importlib
  behavior, the slug-named note kinds and attachment links, the sysup runner
  and attention details, and all 00122 and 00123 findings.
- Upstream `mods.rs` was fetched once. The clone function was read verbatim;
  the second half of the file only as a summary.
- `ground_prd.py`: exit 0 after the fixes (0 missing, 0 unresolved, 0
  unverified). `check_links.py`: 10 rows in the backlog, all forward
  references (five `eligibility` paths to `prds/done/`, five paths 00162
  itself creates). `prds/wip/` and `prds/hold/` do not exist here.
- Budget and tier rules: create-prd step 5.6 was read in full; the
  `autopilot:plan-tasks` skill (0.10.0) only by targeted search of steps 4.5
  to 4.7.
- Not verified: any Herdr behavior beyond `herdr.d.ts`, the spike and the
  fetched function; whether Herdr ignores dot-prefixed directories under
  `mods/` (00160 staging); the Templater claim in 00161 and 00162; GitHub
  issues 272 and 273; where the 800-line file limit is enforced; real vault
  data.

## Decisions applied

No interactive walkthrough ran; every edit is a reversible text change. The
owner may want to change these:

- 00161: naive dates stay UTC digits and the `id_naive_timezone` setting is
  gone. The alternative is `chrono-tz` in Rust plus a zone passed from Python.
- 00161: the doc-ingest feature is gone.
- 00162: `<id>.svg` files and the project resources folder keep their old
  names, and the links to them are not rewritten. The alternative is to
  rename them with the note.
- 00162: `date` wins over the old id when both exist and disagree, as the PRD
  already said; date-only values are skipped.
- 00159: unsupported maps to warned; "requested or running at the deadline"
  and "unexpected version after restart" map to unknown (red).
- 00157: the client re-sends the nonce on "unknown command".
- The engram port plan is now discovery `00163`.

Edits touched `prds/backlog/00156` to `00162` and the discovery rename. Lens A
was re-run on the touched files: headings, order, `Acceptance:` clauses and
frontmatter keys conform.

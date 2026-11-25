# Backlog review - gems - 2026-11-24

Verdict: GO (0 Blocking open)

Branch `feature/config-local-layer-braid`. 18 PRDs in `backlog/`, 0 in `wip/`, 6 in `hold/`.
All 18 come from the agoge run of 2026-11-23, except 00169 (found on 2026-11-24 during PRD 00166).
PRDs 00156, 00159 and 00166 of the same run are done.

Decisions were made by the reviewer under the standing authorization (all edits are reversible
PRD text). No interactive walkthrough ran.

## Map

All PRDs use the `minimal.md` template plus a `## Test Strategy` section (from agoge PRD emission).
All have `design: skip`.

| # | PRD | lines | subsystem | depends on | verdict |
|---|---|---|---|---|---|
| 00149 | docs show dead env form | 68 | docs (config) | - | READY (edited) |
| 00150 | changelog omits nohup SIGHUP change | 77 | CHANGELOG | - | READY |
| 00151 | bim docs stale exit rule | 92 | docs (bim) | - | READY (edited) |
| 00152 | archive deletes already archived note | 91 | bim | - | READY |
| 00153 | jira sync failure dumps traceback | 101 | bim | - | READY (edited) |
| 00154 | interactive import failure exits zero | 87 | bim | - | READY |
| 00155 | doc rules validate mangled error | 79 | bim | - | READY (edited) |
| 00157 | nested env drops yaml siblings | 100 | config resolver | - | READY (edited) |
| 00158 | empty path setting uses cwd | 89 | bim settings | - | READY (edited) |
| 00160 | dotfiles root runs extra commands | 104 | dot | - | READY (edited) |
| 00161 | dot skips damaged gitsecret silently | 112 | dot | 00160 (same file) | READY |
| 00162 | unstage reads argument as pattern | 96 | dot | 00160 (same file) | READY |
| 00163 | missing input stops whole batch | 103 | fren, puc, morph | - | READY (edited) |
| 00164 | terminal escape bytes reach terminal | 99 | console, config | - | READY (rewritten) |
| 00165 | square brackets crash failure message | 87 | console | 00164 (same function) | READY (edited) |
| 00167 | debug flag shows no tool records | 115 | config, shell adapter | 00168 only for test form | READY (edited) |
| 00168 | log record path hard wrapped | 91 | console handler, config | - | READY (edited) |
| 00169 | tool tests reach real updater | 99 | tests only | - | READY |

## Findings

### Blocking (all resolved by an applied edit)

- [00164] E, C: the filter removed control characters inside `format_*`. Six call sites escape
  Rich markup before `format_*` (`click_integration.py:446`, `braid/cli.py:122` and `:126`,
  `bim/doc_cli.py:34`, `bim/note_read_cli.py:182`, `bim/shared/query_paths.py:60`), and 00165 and
  00155 add more. Removal after the escape builds a tag the escape did not see. Measured on
  2026-11-24: `a[\x1b/b].txt` -> escape -> remove ESC -> `a[/b].txt` -> `rich.errors.MarkupError`;
  `x[\x1bbold]y` prints `xy`. So the PRD would have added a new crash for a hostile file name,
  inside its own threat model. -> fails as: rework thrash (a security lens finds the crash after
  the build), or the crash ships. Fix applied: the filter is now `replace_control_chars` and
  replaces each character with `?`. Measured: safe in both orders (`a[?/b].txt` prints as text).
  New requirement and test `test_control_char_inside_brackets_never_becomes_markup`.
- [00165] C: the PRD said "strip control characters first, then escape", but its exact code
  `reporter(escape(message))` escapes first and the filter runs later inside `format_*`. -> fails
  as: rework thrash (implementer and reviewer read two contracts). Fix applied: the order rule is
  removed; with the `?` replacement the order does not matter, and the PRD now says so.
- [00155] B: task 3 acceptance `rg -n "bim doc rules validate" CHANGELOG.md` "prints one line".
  `CHANGELOG.md:485` already holds that text, so the check prints two lines after a correct
  change. -> fails as: rework thrash (an acceptance line that cannot pass). Fix applied: the
  pattern is now `contains square brackets in full`, which is absent today.
- [00149, 00153, 00157, 00158, 00160, 00163, 00167] D (mechanical): `ground_prd.py` reported 16
  `unresolved` rows. All were tokenizer noise: example names in backticks (`MYAPP`, `pic3.jpg`,
  `pwned_root`), the new text that a PRD itself introduces (`BUVIS_MYAPP_DB__HOST`), a parameter
  of a new function (`yaml_value`), dotted forms of a declared symbol (`ConfigResolver.files_read`),
  and two real library names written unqualified (`RequestException`, `ValidationInfo.field_name`).
  No row pointed at a wrong name. -> the skill classes these rows as Blocking. Fix applied:
  backticks removed from example names, new names declared on `New symbols:` lines, library names
  qualified. The gate now exits 0 for the whole backlog.

### Non-blocking (applied)

- [00167] D: text was stale after 00156. The Risk said the working-directory layer is dropped for
  every tool, and the CHANGELOG line listed `cwd` as a layer a user can see. Now: the label stays
  for a settings class that opts in; the CHANGELOG line lists four layers.
- [00164] D: the Problem named the working-directory `config.yaml` as an attack path. 00156
  closed that path. The sentence is corrected and the evidence block has a note.
- [00151] G: the PRD fixed one of two stale sentences in `bim.rst` (`ingest`), and left the twin
  under `bim doc promote`. The twin is now in the PRD, with a replacement text read from the three
  `console.panic` calls at the start of `doc_promote` (read, not run).
- [00168] B: the test instruction was conditional ("unset `COLUMNS` in the test if the environment
  sets it"). It is now definite: the test deletes `COLUMNS`.
- [00164, 00165, 00167, 00168] D: each named 00166 as a pending sibling. 00166 is done; the lines
  say so.

### Non-blocking (open)

- [00164, 00167, 00168] and [00161, 00162]: they add tests to files that are already long
  (`tests/lib/pybase/configuration/test_click_integration.py` 1451 lines,
  `tests/tools/dot/test_git_service.py` 2451 lines). A build on 2026-11-16 met an 800-line limit
  in the work-phase style gate. Not verified whether that gate blocks an addition to a file that
  is already over the limit. If it does, the implementer must put the new class in a new file;
  each acceptance command names the file, so the PRD then needs a small edit.
- [00169] F: it is the last PRD in the drain, but it protects every tool test run from a real
  update check. The risk exists today on every test run. Closes with: build 00169 first by hand,
  or export `BUVIS_DEV_MODE=1` for the drain.

### Questions

None.

## Reshapes

None. Same-subsystem PRDs already sit together: bim 00152-00155, config 00157-00158, dot
00160-00162, console 00164-00168. Every cross-PRD link points at a lower number.

## Gaps

No PRD covers these. They are named by the PRDs as out of scope, or were seen during the review.

- The `--debug` log handler (`CapturingRichHandler`) prints control characters unchanged. 00167
  adds records with config paths and shell commands to that handler, so the surface grows.
- `dot run` builds its own alias from the unquoted `DOTFILES_ROOT` (`src/tools/dot/commands/run/run.py`).
  After 00160 it is the last unquoted use.
- `fren directorize`, `fren flatten` and `fren normalize` keep `click.Path(exists=True, ...)`;
  `morph deblank` keeps the fail-fast loop. After 00163 two patterns exist in the same tools.
- `bim create --json` has an empty stdout and exit 1 on a config error (left by 00166).
- Direct `console.failure(msg)` / `console.panic(msg)` calls with user text and no escape stay
  open after 00165 (only `report_result` and two `doc rules` sites are covered).
- The journeys lane (walter) of the agoge run did not run. Its findings, if any, are not in this set.

## End state after this batch

The bim, dot, fren, puc and morph commands fail with one console line and exit 1 where they now
crash, lie or delete. Config handling keeps YAML siblings and rejects empty bim paths. Console
status lines show control characters as `?` and print square brackets as text. `--debug` names the
config files and shell commands. Tool tests cannot reach the real updater. Still half done: the
items under Gaps, most of all the log handler and `dot run`.

## Frontmatter tuning

None needed. 00149, 00150, 00151 and 00169 name no production path and have `design: skip`, so
the lane classifier should send them to `solo` (read from the create-prd rule text; the classifier
was not run).

## Not checked

- Budget and tier rules of `autopilot:plan-tasks` (steps 4-4.7) were not consulted. Every PRD has
  one module and fewer than 120 lines.
- Manual grounding (`rg`) covered: the console and config anchors of 00164-00168, the dot service
  anchors of 00160-00162, the CLI anchors of 00152, 00154, 00155 and 00163, the docs anchors of
  00149, 00151, 00157, 00158, and the uniqueness of every "prints one line" acceptance pattern.
  Test class and fixture names inside the bim PRDs (00152-00154) rest on the mechanical gate only.
- `check_links.py` found no dangling citation in `backlog/` or `wip/`. Its findings in other
  directories (research, designs, reviews) were not examined.

## Decisions applied

| PRD | Edit |
|---|---|
| 00164 | Rewritten: `replace_control_chars` replaces with `?`; new markup test; stale lines fixed |
| 00165 | Order rule replaced; 00166 marked done |
| 00155 | CHANGELOG acceptance pattern made unique |
| 00167 | `cwd` label wording; CHANGELOG line lists four layers; `ConfigResolver.files_read` declared |
| 00168 | Test deletes `COLUMNS`; 00166 marked done |
| 00151 | `promote` twin sentence added (solution, requirement, task, success criteria) |
| 00149, 00153, 00157, 00158, 00160, 00163 | Grounding-gate cleanups only; no contract change |

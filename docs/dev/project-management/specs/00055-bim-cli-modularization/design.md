# bim: split the cli.py god registry

<!-- design; migrated from PRD 00055 flat file -->

## Implementation

### Module: bim.cli (composition) + per-group modules
- **Location**: `src/tools/bim/cli.py` + `src/tools/bim/cli/<group>.py` (or per-`commands/<group>/` registration)
- **Responsibility**: root composes; each group owns its Click wiring and result rendering via `report_result`.
- **Exports**: `cli` (root group), one `register_<group>(cli)` per group

### Dependencies
- No hard dependency, but sequence after 00054 so the serve/TUI convergence isn't rewriting handlers this PRD is also moving. No dependency on a higher-numbered PRD.

---

<!-- folded from architecture/decisions/00055-bim-cli-modularization-v1-design.md -->

# Design: bim: split the cli.py god registry (00055)

## Architecture fit

`src/tools/bim/cli.py` is the Click composition root for the `bim` CLI tool
(`src/tools/`, "CLI layer" per `AGENTS.md`'s Tool Structure). It sits above the
`bim/commands/<name>/` business-logic tree (each command already has its own
`commands/<name>/` directory: `import_note`, `format_note`, `sync_note`,
`create_note`, `query`, `edit_note`, `archive_note`, `show_note`, `delete_note`,
`serve`, `doc`) and is the only place that wires Click argument/option parsing
to those command classes. This PRD only touches the CLI-registration layer; it
does not move or rename anything under `commands/`.

One precedent for a self-registering module already exists in this exact file:
`bim/doc_rules_cli.py` defines its own local `@click.group("rules")` and
exposes `register_rules_subcommands(doc_group: click.Group) -> None`, which
`cli.py` calls as `register_rules_subcommands(doc)`. This design generalizes
that one working pattern to the rest of `cli.py`, rather than inventing a new
one.

## Module placement

Four new sibling files next to `cli.py` (flat, matching the existing
`doc_rules_cli.py` convention — not a `bim/cli/` package; see Alternatives for
why the package layout was rejected):

| File | Owns | Approx. lines |
|---|---|---|
| `src/tools/bim/doc_cli.py` | the `doc` group + `ingest`/`promote`/`audit` subcommands + `_report_doc_result` helper (all moved verbatim from `cli.py`); keeps the existing `register_rules_subcommands(doc)` call | ~230-260 |
| `src/tools/bim/serve_cli.py` | the `serve` command | ~50 |
| `src/tools/bim/note_write_cli.py` | `import`, `create`, `edit`, `archive`, `delete` (commands that mutate the vault) | ~300-320 |
| `src/tools/bim/note_read_cli.py` | `format`, `sync`, `show`, `query` (commands that read/transform/present, or push to an external system without mutating the local vault) | ~260-280 |

`src/tools/bim/cli.py` shrinks to: module imports, the `@click.group() def
cli(ctx)` definition, four `register_*(cli)` calls, and the `if __name__ ==
"__main__": cli()` guard — no command function bodies remain in it.

**Existing files unchanged in location:** `bim/doc_rules_cli.py` (already
extracted), `bim/__main__.py` (still `from bim.cli import cli`), `pyproject.toml`
`[project.scripts] bim = "bim.cli:cli"` (unaffected — `cli` object still lives
in `bim.cli`, just built from imported pieces instead of decorated inline).

## Interfaces & contracts

### Registration function signatures (mirrors `register_rules_subcommands`)

```python
# bim/doc_cli.py
def register_doc_group(cli: click.Group) -> None: ...   # cli.add_command(doc)

# bim/serve_cli.py
def register_serve_command(cli: click.Group) -> None: ...  # cli.add_command(serve)

# bim/note_write_cli.py
def register_note_write_commands(cli: click.Group) -> None: ...
# cli.add_command(import_note); cli.add_command(create_note)
# cli.add_command(edit_note); cli.add_command(archive_note)
# cli.add_command(delete_note)

# bim/note_read_cli.py
def register_note_read_commands(cli: click.Group) -> None: ...
# cli.add_command(format_note); cli.add_command(sync_note)
# cli.add_command(show_note); cli.add_command(query)
```

Each module declares `__all__ = ["register_<x>"]` (matches
`doc_rules_cli.py`'s `__all__ = ["register_rules_subcommands"]`).

**Circular-import avoidance (the reason this shape, not `@cli.command`
decorators in the sub-modules):** every command in the four new modules is
defined with the free-standing `@click.command(...)` decorator (never
`@cli.command(...)`), exactly like `doc_rules_cli.py`'s `doc_rules` is
`@click.group("rules")`, not `@doc.group(...)`. The sub-module never imports
`cli` from `bim.cli`; it only receives the already-built group object as a
parameter inside `register_*`, called from `cli.py` after `cli` exists. This
is what lets `cli.py` import the four modules at top level with no cycle.

### Root `bim/cli.py` after the split

```python
from __future__ import annotations

import click
from buvis.pybase.configuration import buvis_options

from bim.doc_cli import register_doc_group
from bim.note_read_cli import register_note_read_commands
from bim.note_write_cli import register_note_write_commands
from bim.serve_cli import register_serve_command
from bim.settings import BimSettings


@click.group(help="CLI to BUVIS InfoMesh")
@buvis_options(settings_class=BimSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


register_note_write_commands(cli)
register_note_read_commands(cli)
register_serve_command(cli)
register_doc_group(cli)


if __name__ == "__main__":
    cli()
```

User-facing command names, help text, options, and argument shapes are
unchanged (`bim import`, `bim create`, ... stay top-level; nothing moves under
a new `bim notes ...` subgroup — the "group" here is a code-organization
concept for the CLI-registration layer only, not a new CLI namespace).

### `report_result` swap — per-command call shape

`console.report_result(result, *, success_msg=None, failure_msg="Failed",
on_success=None, on_failure=None)` already exists
(`buvis.pybase.adapters.console.console.py:242`) and is the established
repo-wide convention (real callers today: `zseq/cli.py:52`, plus `puc`, `muc`,
`fren`, `morph`, `pidash`, `dot`, `netscan`, `vuc` — bim's `cli.py` is the one
holdout at 0 uses). It always does `for i in result.info: self.success(i)`
first, then warnings, then success/failure. **Confirmed safe repo-wide**: no
bim command class ever populates `CommandResult.info` (`rg "info="` across
`bim/commands/` and the zettel `application/` layer returns zero real hits —
the two `info=` false-positives were `tzinfo=`), so the extra loop
`report_result` adds is always a no-op for every command below — it introduces
no new output.

| Command (new home) | Current block (lines in old `cli.py`) | Swap |
|---|---|---|
| `import_note` (write) | 81-88: warn loop, `success(output)` if output, else `failure(error or "Import failed")` | `console.report_result(result, failure_msg="Import failed")` — exact match, no callback needed |
| `edit_note` (write) | 399-405 | `console.report_result(result, failure_msg="Edit failed")` — exact match |
| `archive_note` (write) | 438-444 | `console.report_result(result, failure_msg="Archive failed")` — exact match |
| `create_note` (write) | 256-262: `success(output or "Created")` unconditionally on success | needs `on_success=lambda r: console.success(r.output or "Created")` — plain `success_msg="Created"` would always win over real output, which is NOT what the current code does (it prefers `result.output`, falls back to `"Created"` only when empty) — **and** `failure_msg="Create failed"` (the current fallback; `report_result`'s own default is the generic `"Failed"`, which would be new output if `failure_msg` is omitted here) |
| `delete_note` (write) | 511-519: success message is metadata-driven (`deleted_count`), printed only if count > 0 | needs `on_success=lambda r: console.success(f"Deleted {r.metadata.get('deleted_count', 0)} zettel(s)") if r.metadata.get("deleted_count") else None` — **and** `failure_msg="Delete failed"` (same reasoning as `create_note`) |
| `sync_note` (read) | 188-195, inside an existing try/except for `ValueError`/`FileNotFoundError`/`NotImplementedError` (unchanged, not `CommandResult`-shaped) | `console.report_result(result, failure_msg="Sync failed")` for the inner block only; the surrounding `try/except` stays as-is |
| `show_note` (read) | 469-475: success path is `console.print(result.output, mode="raw")`, not `console.success(...)` — different styling | needs `on_success=lambda r: console.print(r.output, mode="raw") if r.output else None`, `failure_msg="Show failed"` |
| `format_note` (read) | 124-147: 3-way branch on `metadata["written_to"]` / diff-or-highlight `result.output` / `metadata["formatted_count"]` | needs a small named `on_success` callback (not a one-line lambda — 3 branches) reproducing the existing branch body verbatim; `failure_msg="Format failed"`. **Callback shape**: a `def _report_format_success(result: CommandResult) -> None:` nested INSIDE `format_note`'s function body (a closure), not a module-level function — the branch body reads `params.diff`/`params.highlight`, both local to `format_note`'s scope, so nesting is what gives the callback access to them without threading extra arguments through `report_result`'s single-arg `on_success` contract. This mirrors how `format_note` already does local lazy imports inside its own body today. |
| `query` (read) | no success/failure/panic block exists today (it reads `result.metadata["rows"]` etc. directly, no `result.success` check) | **exempt** — nothing to swap, PRD's "where the outcome is a CommandResult" clause doesn't apply here |
| `serve` | `cmd.execute()` return value is discarded, no console call at all | **exempt** |
| `doc_ingest` / `doc_promote` | route through the shared `_report_doc_result` helper (outcome-branching: filed/triaged/duplicate/strict-panic — not a binary success/fail model) | **stays hand-rolled**, moved verbatim into `doc_cli.py`; `report_result`'s binary model can't express the 3-way outcome branch without becoming `_report_doc_result` again |
| `doc_audit` | 715-724: failure branch is a plain `console.failure`; success branch renders a report then prints a path-derived success message | needs a small named `on_success` callback (render + success line), `failure_msg="audit failed"` |

Every `on_success`/`failure_msg` value above is copied verbatim from the
existing message strings — do not paraphrase them, the PRD requires
byte-identical output.

### Import placement per new module

Most relocated commands call `get_settings(ctx, BimSettings)` (10 call sites
across all four target modules — `cli.py:48,59,178,227,308,429,537,588,643,691`)
and several construct `Path(...)` directly or reference it via
`click.Path(path_type=Path)` — `BimSettings` and `Path` are NOT root-only
imports; each module below must import both itself:

Every one of the four new modules defines Click decorators (`@click.command`,
`@click.option`, `@click.argument`, `@click.group`, `@click.pass_context`,
`click.Path`/`click.Choice` as option types) — **all four need `import
click`**, not just `cli.py` (the design's first import-fix pass fixed the
`BimSettings`/`Path` gap but missed this; caught in review dispatch 2):

- `note_write_cli.py`: `click`, `Path`, `Any` (used in `edit_note`'s and
  `delete_note`'s `**kwargs: Any`), `BimSettings`, `ArchiveNoteParams`,
  `DeleteNoteParams`, `EditNoteParams`, `apply_generated_options`,
  `get_settings`, `resolve_paths` (`bim.shared.query_paths`), `console`.
- `note_read_cli.py`: `click`, `Path`, `Any` (used in `format_note`'s and
  `query`'s `**kwargs: Any`, and `sync_note`'s `jira_adapter: dict[str,
  Any]`), `BimSettings`, `CommandResult` (type hint on `format_note`'s nested
  `_report_format_success(result: CommandResult) -> None` closure — see the
  `report_result` swap table), `FormatNoteParams`, `QueryParams`,
  `apply_generated_options`, `get_settings`, `resolve_paths`, `console`, `time`
  (for `query`'s `time.perf_counter()`), `present_query_result`
  (lazy-imported today inside `query`, stays lazy per the repo's "lazy imports
  in CLI handlers" convention).
- `serve_cli.py`: `click`, `Path`, `BimSettings`, `get_settings`. `console` is
  not currently used by `serve` itself — verify at implementation time and
  drop unused imports (no unused imports per Testing conventions).
- `doc_cli.py`: `click`, `Path`, `BimSettings`, `sys` (isatty check in
  `doc_ingest`), `CommandResult` (type hint on `_report_doc_result`),
  `get_settings`, `console`, `register_rules_subcommands` from
  `bim.doc_rules_cli` (unchanged import, just now a sibling-to-sibling import
  instead of leaf-to-root).
- `cli.py`: only `click`, `buvis_options`, `BimSettings` (needed by
  `@buvis_options(settings_class=BimSettings)` on the root `cli` group itself),
  and the four `register_*` imports remain. `Path`, `Any`,
  `apply_generated_options`, `get_settings`, `CommandResult`, and all
  `bim.params.*`/`bim.commands.*` imports move to whichever new module
  actually uses them (per-module lists above) — implemented literally without
  those additions, every relocated command raises `NameError` on first
  invocation.

This list is now exhaustive per name-by-name verification against every
relocated command's body — treat it as the single source of truth for what
each new module imports; do not re-derive it from the old `cli.py`'s
top-of-file import block, which mixed all 13 commands' needs together.

## Data flow

Unchanged at runtime: `bim <cmd>` → Click dispatches to the command function
(now defined in one of the four new modules instead of inline in `cli.py`) →
the function still does its own lazy `from bim.commands.<x> import Command<X>`
+ `from bim.dependencies import get_*` + `cmd.execute()` → `CommandResult` →
console output. The only thing that changes is which `.py` file physically
holds the Click decorator + function body; the call graph beneath `execute()`
is untouched. Registration happens once at import time: `bim/cli.py` imports
the four modules (which only *define* free-standing commands, no side
effects), then calls `register_*(cli)` in sequence, each doing a plain
`cli.add_command(...)`.

## Reuse inventory

- `console.report_result` — `buvis.pybase.adapters.console.console.py:242`.
  Existing real callers to copy the calling convention from:
  `src/tools/zseq/cli.py:52` (`console.report_result(result)`, the simplest
  case), plus `puc`, `muc`, `fren`, `morph`, `pidash/cli.py` (uses
  `on_failure=_render_status_failure`, the precedent for this PRD's
  `on_success=`/`on_failure=` callback usage), `dot`, `netscan`, `vuc`.
- Self-registering Click sub-module pattern — `bim/doc_rules_cli.py` (already
  in the repo, doc-rules group registers onto `doc` via
  `register_rules_subcommands(doc_group: click.Group) -> None`). This design
  copies that exact function-signature shape for all four new modules.
- `bim.shared.query_paths.resolve_paths` — existing shared helper, already
  imported once in `cli.py` and used by 6 of the 9 note commands; no new
  helper needed, just re-imported in both `note_write_cli.py` and
  `note_read_cli.py`.
- Nothing found for "split a Click CLI into per-group modules with a
  `register_<x>(parent)` signature" beyond `doc_rules_cli.py` itself — greps
  tried: `rg -rn "click.Group" src/tools/`, `rg -rn "add_command" src/tools/`,
  `rg -rn "def register_" src/tools/` (only hit is `doc_rules_cli.py`'s own
  `register_rules_subcommands`). No other tool in the repo has a CLI large
  enough to need this (next-largest is `pidash/cli.py` at 185 lines, `dot/cli.py`
  at 151 — both well under the split threshold).

## Alternatives considered

1. **Smallest-diff: one sibling file** (`bim/commands_cli.py` holding all of
   notes + serve + doc, `cli.py` shrinks to composition + one `register_*`
   call). Rejected as the chosen design's fallback-if-time-constrained: it
   satisfies "cli.py becomes composition-only" with the least code movement,
   but reintroduces a ~550-line file that still mixes four unrelated command
   families in one module — the same review-friction problem this PRD exists
   to fix, just renamed. Doesn't honor "organize by feature/domain"
   (`AGENTS.md` File Organization).
2. **Package conversion**: turn `cli.py` into `bim/cli/__init__.py` +
   `bim/cli/notes_write.py` + `bim/cli/notes_read.py` + `bim/cli/serve.py` +
   `bim/cli/doc.py`. This is literally one of the two locations the PRD text
   suggests (`bim/cli/<group>.py`). Rejected: it still resolves fine through
   `bim.cli:cli` and `from bim.cli import cli` (both work identically against
   a package), but it diverges from the one proven, already-in-use repo
   convention (`doc_rules_cli.py`, a flat sibling file) for zero functional
   gain, and touches one more thing (module → package rename) than necessary.
3. **Chosen: four flat sibling files**, each following the
   `register_<x>(parent: click.Group) -> None` shape `doc_rules_cli.py`
   already established. Matches "Organize by feature/domain": mutating note
   ops, read/present note ops, serve, and doc are four genuinely different
   concerns. Every new file lands at 50-320 lines — solidly inside the
   200-400-typical / 800-max guidance, with headroom before any of them needs
   splitting again.

## Risks & edge cases

- **Output-fidelity risk on the `report_result` swap, AND a test-mocking trap
  that defeats the safety net** (caught by review dispatch 2 — an earlier
  draft of this section claimed the existing tests would catch any wording
  drift "for free"; that claim was wrong, see the corrected Test strategy
  outline below for why and how it's fixed). The per-command table above is
  still written to be copied verbatim, but copying it verbatim is not
  sufficient by itself — the test files must ALSO be migrated from
  whole-object console mocking to leaf-method mocking, or the existing
  assertions silently stop testing anything (they'd pass even if the
  rendered text were wrong, because they'd be asserting on a mock method that
  is never called anymore). Run the full `bim` suite after every single
  command's swap, not once at the end.
- **Circular import**: covered under Interfaces & contracts — the
  free-standing-`@click.command` + `register_*(parent)` shape is what avoids
  it. A naive first attempt that does `from bim.cli import cli` inside e.g.
  `note_write_cli.py` and decorates `@cli.command(...)` directly WILL create
  an import cycle (`cli.py` imports `note_write_cli`, which imports `cli.py`)
  — flag this explicitly during implementation review.
- **`query`'s missing success/failure block** is intentional, not an oversight
  in this design — confirmed above it has no `result.success` check today at
  all. Do not "fix" this by adding one; that would be new behavior outside
  this PRD's stated non-goal ("No command's user-facing behavior or output
  changes").
- **Likely next changes after this PRD** (per AGENTS.md's tail-tools-are-
  maintenance-only note, `bim` is the tool most likely to keep growing):
  (a) `doc_cli.py` could itself outgrow ~400 lines as the doc subsystem gains
  commands — the `doc_rules_cli.py` extraction already shows the template for
  splitting it further (e.g., a future `doc_promote_cli.py`); this design
  doesn't box that in. (b) A new mutating note command has an obvious home
  (`note_write_cli.py`) and a new read/present command has an obvious home
  (`note_read_cli.py`) — the write/read split was chosen partly so this
  decision stays unambiguous for the next contributor.

## Test strategy outline

**Two independent test-migration problems, both confirmed by grep against the
real test files (review dispatch 2 caught both — an earlier draft of this
section missed them):**

1. **66 `patch("bim.cli.<name>")` string-target mocks across 7 files** break
   the moment the patched name (`console`, `get_settings`, or a command
   function) is no longer an attribute of the `bim.cli` module namespace.
   Confirmed count via `rg -c 'patch\("bim\.cli\.' tests/tools/bim/ -r`:
   `test_bim_cli_handlers.py` (34), `test_cli.py` (9), `test_query.py` (5),
   `test_create_note.py` (6), `doc/test_cli_ingest.py` (6),
   `doc/test_cli_promote.py` (3), `doc/test_cli_audit.py` (3) — 66 total,
   `test_edit_note.py` has zero (its only `bim.cli` reference is `from
   bim.cli import cli`, unaffected). `mock.patch` resolves a string target by
   importing the module and looking up the attribute at patch time — once
   `console`/`get_settings`/a command are no longer imported into `cli.py`,
   `patch("bim.cli.console")` raises `AttributeError`, not a silent no-op.
2. **Whole-object console mocking bypasses `report_result` entirely, so
   existing assertions would pass without testing anything.** Every one of
   those 66 sites (well, the `console`-target subset of them) does
   `patch("bim.cli.console")` — replacing the ENTIRE singleton with a
   `MagicMock` — then asserts e.g. `mock_console.success.assert_called_once_
   with("Formatted note written to /tmp/out.md")`
   (`tests/tools/bim/test_bim_cli_handlers.py:22,35`, verified directly).
   Once a command calls `console.report_result(result, on_success=...)`
   instead of `console.success(...)` directly, `mock_console.report_result`
   is the only thing that gets called on that mock — `mock_console.success`
   is never invoked (the real dispatch logic that would call it lives on the
   REAL `ConsoleAdapter` class, which the mock has replaced wholesale), so
   `mock_console.success.assert_called_once_with(...)` fails with "expected
   call not found." Simply retargeting the patch string (fixing problem 1
   alone) does NOT fix this — it's an independent defect in HOW the tests
   mock, not just WHERE.

**The fix for both, applied together per test file:**

- Retarget every `patch("bim.cli.X")` to `patch("bim.<new_module>.X")`, where
  `<new_module>` is whichever of `note_write_cli`/`note_read_cli`/
  `serve_cli`/`doc_cli` now owns the command under test (per the Module
  placement table above — e.g. `test_create_note.py` and the `TestCreate*`
  classes target `bim.note_write_cli`, `test_query.py` and `TestQuery*`
  target `bim.note_read_cli`, the three `doc/test_cli_*.py` files target
  `bim.doc_cli`).
- Where the patch target is `console` specifically AND the test asserts on a
  leaf method (`.success`/`.warning`/`.failure`/`.print`/`.confirm`), stop
  patching the whole object. Patch only the leaf method actually asserted on:
  `patch("bim.<new_module>.console.success")` (or `.warning`/`.failure`).
  Because `console` is a true module-level singleton (`ConsoleAdapter()`,
  `console.py:348`) — the same object reachable from every module that
  imports it — patching a leaf attribute through any importing module's path
  patches the one real instance everywhere, and `report_result`'s internal
  `self.success(...)`/`self.warning(...)`/`self.failure(...)` calls
  (`console.py:260-272`) now hit the patched leaf method exactly as they did
  before the swap. The assertion lines themselves (`mock_success.assert_
  called_once_with(...)`) do not need to change — only what gets patched and
  the local variable name receiving it.
- `mock_console.report_result.assert_called_once_with(...)` is NOT an
  acceptable replacement for the leaf-mock fix above for commands using
  `on_success`/`on_failure` callbacks — the callback itself is a closure
  defined inside the command function, so asserting on `report_result`'s call
  arguments can prove the LAMBDA WAS PASSED, not what it renders. Leaf-method
  patching lets the real `report_result` actually invoke the (unpatched, real)
  callback, which then calls the patched leaf method with the real computed
  text — that's what proves output fidelity.

**Sequencing:**

1. **Before moving anything**: run `uv run pytest -m bim` and `uv run mypy
   src/tools/bim/` once to capture the current-green baseline.
2. **Mirror the source split 1:1, moving test classes verbatim** (location
   only — the class bodies don't change beyond the patch-target/leaf-mock fix
   above, since `CliRunner().invoke(cli, [...])` doesn't care which module
   physically defines a command as long as it's registered on the same `cli`
   object):
   - `tests/tools/bim/test_note_write_cli.py` ← `TestImportCommand`,
     `TestImportInteractiveHelpers`, `TestCreateCommand`, `TestDeleteCommand`
     (moved out of `tests/tools/bim/test_cli.py`).
   - `tests/tools/bim/test_note_read_cli.py` ← `TestShowCommand`,
     `TestFormatCommand`, `TestSyncCommand`, `TestQueryCommand` (moved out of
     `test_cli.py`).
   - `tests/tools/bim/test_cli.py` keeps only `TestBimCliHelp` (tests the
     composed root `cli` group's `--help` output — this is genuinely a
     root-composition concern, stays where it is).
3. **Apply the patch-target + leaf-mock fix** to all 66 sites across the 7
   files named above, in the same pass as each command's `report_result`
   swap (not as a separate cleanup pass — a test file left on
   `patch("bim.cli.console")` after its command moves is red, so there is no
   working intermediate state to defer this to).
4. **Fix the two direct-function-import sites** (the only tests that reach
   past `CliRunner` into a specific command function object, independent of
   the 66 `patch()` sites above):
   - `tests/tools/bim/test_create_note.py`: `from bim.cli import create_note`
     → `from bim.note_write_cli import create_note`.
   - `tests/tools/bim/test_query.py`: `from bim.cli import query` →
     `from bim.note_read_cli import query`.
   - Confirmed via `rg "from bim.cli import"` across `tests/tools/bim/` that
     no other test file does a direct function-object import.
5. **After each extraction step** (doc, serve, note-write, note-read, in that
   order — matches the PRD's Phase 0 "one group first" / Phase 1 "remaining
   groups"), re-run `uv run pytest -m bim` and `uv run mypy src/tools/bim/`
   before moving to the next group. This is the PRD's own "characterize first
   if unsure" instruction applied per-step rather than once at the end, so a
   regression is caught against the single group that introduced it. Because
   of item 3 above, a group's `report_result` swap and its test-mock fix land
   in the same step — there is no green intermediate state where the source
   changed but the tests didn't.

## Review log

- non-blocker (dispatch 1): `sync_note` is placed in `note_read_cli.py` under
  the "non-mutating" criterion, but `CommandSyncNote._create_issue`
  (`bim/commands/sync_note/sync_note.py:104-114`) calls
  `atomic_write_text(path, formatted_content)` — it does write the new Jira
  link/log entry back into the local zettel file, contradicting the
  read/write split's own stated criterion. Not fixed now (module placement
  still works either way; `sync_note` genuinely straddles read+write). Flag
  for `/plan-tasks` or the implementor: either move `sync_note` to
  `note_write_cli.py`, or keep it in `note_read_cli.py` and drop the
  "non-mutating" framing from the table (the file-size split itself is
  unaffected — 4 vs 5 commands in each of the two note modules either way).
- question (dispatch 1): `doc_ingest`/`doc_promote` are exempted from the
  `report_result` swap because "report_result's binary model can't express
  the 3-way outcome branch without becoming `_report_doc_result` again" — but
  the same table swaps `format_note` and `doc_audit` to `report_result` via a
  named multi-branch `on_success` callback, which is the identical technique
  that could express `_report_doc_result`'s filed/triaged/duplicate/strict
  branching too. PRD must-have #2 states no carve-out for multi-way outcomes.
  Left as a question, not fixed: leaving 2 of 13 commands hand-rolled still
  satisfies Phase 1's acceptance criterion ("`report_result` has real
  callers") via the other 9-10 commands. `/plan-tasks` should decide whether
  to also swap `_report_doc_result`'s callers or keep it exempt.
dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 1, question 1

- dispatch 2 fixed 4 blockers: (1) `click` and `Any` were still missing from
  the per-module import lists (only `BimSettings`/`Path` had been added after
  dispatch 1) — every module now lists `click` and both note modules list
  `Any`. (2) 66 `patch("bim.cli.<name>")` sites across 7 test files would
  `AttributeError` once the patched names leave `cli.py`'s namespace — the
  Test strategy outline now specifies the exact per-file retarget rule. (3)
  those same tests mock the whole `console` singleton then assert on a leaf
  method (`mock_console.success...`), which the `report_result` swap makes
  silently untested (the leaf method is never called once `console` itself is
  fully mocked) — Test strategy outline now mandates leaf-method patching
  instead, with the mechanism spelled out. (4) `create_note`/`delete_note`'s
  `report_result` calls were missing `failure_msg="Create failed"`/`"Delete
  failed"`, which would have silently changed failure-path output to
  `report_result`'s generic `"Failed"` default — added to the swap table.
  The one question raised (format callback's access to `params.diff`/
  `params.highlight`) was resolved inline as part of the fix: specified as a
  nested closure inside `format_note`, not a module-level function.
dispatch 2 (codex): cardinal-sin 0, blocker 4, non-blocker 0, question 1

- dispatch 3 (codex, verification pass) confirmed all 5 prior fixes (1 from
  dispatch 1, 4 from dispatch 2) as correct and complete, and found 1 new
  blocker: `note_read_cli.py`'s import list was missing `CommandResult`,
  needed for the `format_note` nested closure's `def
  _report_format_success(result: CommandResult) -> None` type hint (mypy
  failure, and a runtime `NameError` without `from __future__ import
  annotations` deferring the hint). Fixed — added to the import list. Also
  caught and fixed a minor inaccuracy: the design said "11" `get_settings`
  call sites; the real count is 10 (`cli.py:48,59,178,227,308,429,537,588,
  643,691`).
- non-blocker (dispatch 3, not fixed): two tests
  (`tests/tools/bim/test_bim_cli_handlers.py:270-278,499-504`) stub
  `mock_console.confirm.return_value` without asserting on it, on a
  whole-object `patch("bim.cli.console")` mock — both paths return before
  reaching `report_result`, so this is safe as-is, but it's inconsistent with
  the leaf-mock mandate's "asserts on a leaf method" trigger wording. Left as
  a wording clarification for the implementor, not a functional defect: the
  Test strategy outline's leaf-mock rule already only fires where
  `report_result` is actually in the call path, and `confirm()` happens
  before that in both cases.
dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 2, question 0

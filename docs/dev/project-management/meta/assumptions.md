# Assumption ledger - PRD 00150

## 1: Add tx settings and confined tiromex path resolution

Test author:
- An invalid-JSON or empty `state.json` and non-UTF-8 bytes count as unreadable, so `read_last_maintain` returns `None`.
- `read_last_maintain` returns `""` unchanged; `staleness` treats it as never run.
- A dangling symlink as the tiromex folder is refused, because `is_symlink()` is true.
- Folder names `..atlas` and `.tiromex` are valid: one part, not `.` or `..`.
- `confine("")` raises, because it resolves to the vault root.
- `to_vault_rel` accepts files inside the vault but outside the tiromex folder; a file outside the vault is untested.
- `XDG_STATE_HOME` follows the XDG spec: an empty or relative value falls back to `~/.local/state`.
- A failed assignment on a frozen model raises pydantic's `ValidationError`.
- `BimSettings.model_validate` with an explicit mapping wins over the environment.
- A regular file at `<zettelkasten>/tiromex` is not refused by `resolve_tiromex` (the contract is silent).

Implementor:
- `confine` accepts the folder path itself (`notes/tiromex`).
- `iter_note_files` leaves out directories whose names end in `.md` and returns each path as found.
- `to_vault_rel` does not resolve `file` before making it relative.

## 2: Add the tiromex note format reader

Test author:
- `sources` reads `source` from `data.reference` (the backmatter), like `relations` and `parents`.
- `body_lines` treats a whitespace-only line as blank and returns kept lines unstripped.
- `read_note` passes on the `ValueError` from `parse_note`.
- `parse_links` returns `[]` for `""` and `[]`; `None` and other non-strings are untested.
- `link_file` does not strip `.md` or `#` from a target.
- With backmatter, the raw body runs up to and including the newline before the `---` line.
- The DST test relies on `time.tzset` honouring POSIX TZ rules.

Implementor:
- bim parser errors are passed on as raised, without the note path; only the missing-front-matter error names the path.
- `sources` keeps empty parts as written (`""` gives `[""]`).
- `parse_links` and `sources` skip values that are not strings; `None` means no links.
- The enums are `(str, Enum)`, not `StrEnum`.

## 3: Add the tiromex mechanical validator

Test author:
- "H1 followed by a `- parent::` line" means H1, the `---` separator, then `- parent::`.
- "Blank" for `required-field` includes whitespace only.
- `transitive-cycle` is checked as once per relation on a note inside the cycle; which member is not pinned.
- `target: null` on a disagreement doubt counts as having the key and gives `doubt-target-shape`.
- A doubt whose `target` is a string gets only `doubt-target-shape`, no graph rule.
- A non-string tag triggers no rule; the other tags are still checked.
- An outside target that exists gives only `path-confinement`, no dangling rule.
- In `source-shape`, the root is the text between `mirror:` and the first `/`.
- The `required-field` message names the missing field as a whole word.

Implementor:
- When `id`, `title` or `type` is missing or blank, the rules that read it are skipped; only `required-field` reports.
- Enum and set membership is checked only for strings; `tags` that is not a list is not checked.
- `link-shape` fires when a relation or `parent` key is present but holds no wikilink, including an empty value.
- `source-shape` passes an empty root name (`mirror:/x`) or an empty path part.
- `dangling-doubt-target` and its confinement check apply to any doubt whose `target` is a mapping with a string `to`, whatever the mode (as the source).
- On index notes, relation targets get `path-confinement` only, no dangling check.
- Message wording is the implementor's own, after the source messages where the rule exists there.

Per-task review (LOW, not fixed): `_first_cycle` is recursive, so a transitive chain deeper than about 1000 notes raises `RecursionError` (ported from the source).

## 4: Add a stderr keyword to the console adapter warning and failure

Test author:
- `capsys` output is not a terminal, so Rich prints no colour codes on either stream; the stdout/stderr comparison relies on it.
- "Built at call time" is tested from outside: output follows whatever `sys.stderr` is when the method is called.
- The default stdout console and the call-time stderr console pick the same width in tests.

Implementor: none.

Per-task review (LOW, not fixed): `warning` and `failure` repeat the same target-console expression.
Pre-existing, not touched: `test_valid_dir_passes` and `test_valid_file_passes` in `test_console_adapter.py` have no assertion (shape check).

## 5: Add claim collection and the tx validate and export-claims commands

Test author:
- A well-formed claim is a mapping whose `id` and `statement` are present, not `None` and not blank (orchestrator ruling after the adversary round); the whitespace-only case is not pinned.
- `collect_claims` sorts by path itself; claim order inside a note is kept as written.
- `validate --json` puts the JSON in `result.output` for a failed result too.
- `generated` equals `now.isoformat()`.
- The `<out>` in the refusal message is `str(out)` as given, not `dest`.
- A failure to create or write the destination returns a failed `CommandResult`.

Implementor:
- An `assent` or `lifecycle` key that is present but null is written as `"None"`; the default applies only when the key is missing (as the klyreon source).
- A failed write returns `error="cannot write <dest>: <exc>"` (own wording).
- The skip warning reuses the `ValueError` text from `read_note`, which already starts with the path, so the path shows twice.
- The refusal error ends with the vault root and the source's explanation sentence.

## 6: Add the tx new and status commands

Test author:
- Status line 1 is `tiromex: {paths.folder}` (absolute path).
- The `lifecycle:` and `assent:` lines join `k=v` with `", "`; order is compared as dicts.
- `status` returns `success=True` even when maintenance is stale or git is absent.
- A status warning contains the vault-relative path of the unparseable file.
- A day count equal to `window_days` is fresh; the count is whole elapsed days.
- "Captured output" means `subprocess.run(..., capture_output=True)`.
- Every doubt with mode `disagreement` on a concept note counts as open (orchestrator ruling, as the source).
- The collision test waits for the real clock second to change (up to about 1 s); the use case's `time.sleep` is patched to record calls.
- The `refusing to write an invalid note:` path is not tested.

Implementor:
- The template takes the title from `answers["title"]`.
- The git line reads "tracked" only when the exit code is 0 and stdout is `true`.
- Inbound and `supports` links match a note when `link_file(link.target) == note.path` exactly, with no path resolving.
- A prune candidate must be strictly older than the window.
- Lifecycle and assent counts print sorted by key.

Per-task review (LOW, not fixed): the prune count rescans every note's relations per concept note (quadratic); the lifecycle and assent counters repeat one expression.

## 7: Wire the bim tx CLI group, manifest, skill exception and changelog

Test author:
- A missing `--title` or a value outside a Choice exits 2 (Click's usage error).
- The `get_tiromex_paths` panic text and the validate text failure are checked in combined output; their stream is not pinned.
- Text that goes through Rich is matched with whitespace removed (80-column wrapping).
- The SKILL.md exception paragraph follows the approval rule after one blank line and holds the phrase "may read and write without asking".
- A state stamped exactly N days before now counts as N whole days.
- The atomic write of `--out` is not tested at CLI level.
- The first strengthen dispatch hung with no output and was re-dispatched once.

Implementor:
- `tx_cli.py` imports the `--type` and `--concept-type` choice values from the tx format module at module level, so `bim --help` now loads the zettel parser and formatter modules.
- `validate` uses `settings.tx.max_zettel_body_lines`; `status` uses the three `settings.tx` maintenance and prune values.
- The group callback also runs before a subcommand's `--help`, so `bim tx new --help` can print the staleness warning on stderr.
- SKILL.md wording for the conflict shapes comes from the design and the old klyreon spec.
- AGENTS.md keeps "Two sanctioned exceptions" and adds "A third is ...".

Per-task review (LOW, not fixed): the staleness warning also fires on `--help` and usage errors; `_resolve_paths` returns an optional and four handlers repeat a `None` guard; the warning wording dict is rebuilt per call.

## 8: Write the tiromex format specification and bim tx docs

Implementor:
- The new rst section uses ` - ` where the existing option lists use an em dash.
- The tx settings table sits inside the `bim tx` section, not in the top Configuration table.
- `tx.backend`, `tx.max_sources_per_run`, `tx.source_timeout_seconds` and `tx.git_identity_*` are described as reserved for tx runs; no shipped command reads them yet.
- Spec examples use `YYYY-MM-DDTHH:MM:SS+HH:MM` dates and an unquoted `id`.
- `<root>` in `mirror:<root>/<path>` is described as the name of a source mirror; this version checks only the shape.

## 1 (continued)

Per-task review (LOW, not fixed): `confine` does not turn a symlink-loop `RuntimeError`/`OSError` from `Path.resolve()` into `ValueError`.

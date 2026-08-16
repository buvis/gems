# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **pybase**: `atomic_write_text` / `atomic_write_bytes` — new public helpers in `buvis.pybase.filesystem` for crash-safe (tempfile + fsync + `os.replace`) writes.
- **bim**: `doc` gains a `claim_max_age_minutes` setting (default 60, a whole number of minutes, rejects zero or less). An ingest claim left behind by a run that died without cleaning up is treated as abandoned once it passes that age, so re-running the document proceeds instead of reporting it as a duplicate forever. The reclaim is a compare-and-delete that never removes a live claim another run legitimately took over in the meantime, and it tolerates a corrupt or unreadable stored `claimed_at` timestamp (including one stored as a BLOB) by treating the claim as abandoned instead of crashing the run.
- **bim**: `doc ingest` now recognises a resent copy of a document that is still awaiting triage review in `_triage/` as a duplicate, instead of re-running the whole pipeline on it. The duplicate sidecar and the recorded dedup entry name it as pending review rather than as an already-filed document.

### Security

- **bim**: `serve` confines every request-derived filesystem path to the configured vault and archive directories, so its API can no longer read, overwrite, delete, open, or import files outside them. Paths outside the vault are rejected with 403.
- **bim**: `serve` requires a per-run auth token (`X-Buvis-Token`) on its mutating and query-executing routes, and installs a Host allowlist so a web page cannot reach the default loopback-bound server by DNS rebinding. The WebUI sends the token automatically; read-only `GET` routes stay token-free.
- **bim**: `serve` no longer embeds the auth token in the page it serves when bound to a non-loopback host, so a LAN caller (or a DNS-rebinding page) can no longer read the token and gain write access; the token is printed to the operator's console instead.
- **dot**: `rm` no longer interpolates the filename unquoted into its shell commands, closing a shell-injection hole for a dotfile name containing spaces or shell metacharacters (`;`, `` ` ``, `$()`).

### Fixed

- **bim**: `serve` returns 404 instead of crashing with a 500 when its static directory has no `index.html`, and warns instead of silently dropping the auth token when the served page has no `</head>`.
- **bim**: `serve` answers a request whose auth-token header contains a non-ASCII character with the documented 401 instead of crashing into a 500 with a raw stack trace.
- **bim**: `serve` path confinement expands `~` in both the request path and the configured vault/archive directories, so a tilde-form directory no longer locks out every legitimate path with a 403.
- **bim**: `import` writes the imported note atomically, so an interrupted import (crash, kill, disk full) no longer truncates an existing note.
- **pybase**: atomic writes clean up their temp file when interrupted by Ctrl-C, no longer leak a file descriptor if the permission step fails, and no longer replace the real write error with a cleanup error.
- **zettel**: note saves are now atomic — the single write path behind `bim edit`, note creation, archive, the TUI, and the WebUI's action endpoint; an interrupted save no longer truncates the note.
- **bim**: `sync`, `format`, and the WebUI's PATCH endpoint now write notes atomically instead of each using their own bare write, so an interrupted write no longer truncates them.
- **pybase**: updater state is now written atomically, so an interrupted update can no longer leave the shared state JSON torn.
- **bim**: `doc promote` no longer overwrites an already-filed document and its zettel when a second document resolves to the same canonical filename — it files the newcomer under the next free name, and fails without writing anything if no free name is available.
- **bim**: `doc promote` reports a filesystem failure while picking the filed name (read-only vault, permissions, disk full) as a plain error message instead of crashing with a stack trace.
- **bim**: interrupting a `doc ingest` with Ctrl-C no longer parks the document permanently. The claim is released on every exit path, so a re-run proceeds instead of reporting the document as a duplicate that never gets filed.
- **bim**: a document filed through `doc` triage and then `doc promote` is now recognised as a duplicate when the same source arrives again (a re-download or re-export), instead of re-running the whole pipeline and filing a second archive copy under an incremented name.
- **dot**: `rm` on an encrypted (git-secret) file now only untracks it, matching the plain `rm --cached` path — it no longer also deletes the decrypted plaintext copy from disk. The plaintext keeps its `.gitignore` entry, so the surviving cleartext secret is not offered for staging by the next `dot add`, and the committed `<file>.secret` ciphertext is untracked too, so the file really does leave the repo. If untracking the ciphertext fails, the error now says the git-secret mapping was already changed and names the command that restores it, instead of leaving a blind retry to silently take the plaintext path.

## [0.12.6] - 2026-08-06

### Security

- **deps**: bump `cryptography` 49.0.0 -> 50.0.0 (PYSEC-2026-3552), pulled in by `pdfminer.six`.

## [0.12.5] - 2026-08-06

### Fixed

- **gems**: publish a source distribution alongside the wheels, so package indexes that list versions from `.tar.gz` filenames (Artifactory mirrors, mise's `pipx` backend) can see new releases.

## [0.12.4] - 2026-08-02

### Added

- **morph**: `morph pdf2png` command — renders every page of a PDF into one tall stacked PNG (poppler `pdftoppm` + Pillow).

## [0.12.3] - 2026-07-19

### Fixed

- **sysup**: `sysup mac` no longer reports a failed helm step on machines with no helm repositories configured — an empty `helm repo list` now reports "no helm repos configured, skipping" instead of helm's "no repositories found" error.

## [0.12.2] - 2026-07-19

### Added

- **sysup**: `sysup mac` caches sudo credentials upfront (`sudo -v` plus a background refresh) so brew cask installs no longer stop for a password mid-run; the prompt now appears once, predictably, at the start.

## [0.12.1] - 2026-07-19

### Fixed

- **deps**: bump `cryptography`, `idna`, `msgpack`, `pillow`, `pip`, `pydantic-settings`, `soupsieve`, `starlette` to patched versions, closing 20 known CVEs flagged by `pip-audit`.
- **sysup**: `sysup nvim` no longer crashes with a raw traceback when a concurrent `mise upgrade` replaces the nvim binary mid-run — the path is re-resolved before each step and a vanished binary reports a failed step instead. Terminal escape sequences are also stripped from the mason timeout message.
- **sysup**: the pip step now upgrades every mise-managed Python (PATH `python3` as fallback) instead of sysup's own interpreter — under a mise pipx install that venv is uv-built and has no pip, so `sysup mac`/`sysup pip` always failed with "No module named pip". Interpreters without pip are reported and skipped.
- **sysup**: `sysup mac` runs `mise upgrade` last. Running it early deleted replaced tool version directories still referenced by the shell's PATH, making later steps falsely report `uv not found` / `helm not found`.

## [0.12.0] - 2026-05-11

### Added

- **pidash**: bundled hook runtime (``pidash hooks run <event>``) plus ``pidash hooks install``/``uninstall``/``status`` admin commands. Run ``pidash hooks install`` after ``pip install buvis-gems[pidash]`` to wire the autopilot dashboard hooks into ``~/.claude/settings.json`` in one step. Existing legacy entries (``python3 ~/.claude/hooks/<name>.py`` paths from the dotfiles repo) are detected and replaced during install, with unrelated hook entries preserved in place.
- **bim**: `bim doc audit` command — read-only walk of the Business folder reporting drift between filed PDFs and zettels. Checks per spec §9: filename canonical, issuer registered, doc-type valid, per-issuer zettel exists, OCR present, sha256 in state.db. Plus rule-engine checks: registry loadability, priority conflicts, freshness (90-day default). Writes a structured JSON report to `<state_dir>/audit/<iso-timestamp>.json`; the report's `legacy_layout_zettels` array is the input contract for the future migration command.

### Fixed

- **pidash**: `pidash hooks install` now fails with a clear error and leaves `settings.json` untouched when the existing `hooks` key is not a JSON object (array, string, or `null`). Previously it silently overwrote the value with `{}` and rewrote the file, which could discard the user's hook config.
- **pidash**: bundled hooks (`set-attention`, `clear-attention`, `update-tasks`, `sync-agent-return`) now write `dev/local/autopilot/state.json` atomically via tempfile + `os.replace`. Previously a hook killed mid-write (SIGKILL, disk full) could leave a truncated `state.json`, which is the source of truth for every subsequent hook and the dashboard. The session-file writer (`~/.pidash/sessions/{id}.json`) was already atomic.
- **pidash**: bundled session hooks (`mirror_to_session_dir`, `cleanup-session`) now reject a `session_id` containing an embedded null byte instead of propagating `ValueError` from `tempfile.mkstemp`. The existing `except OSError` did not catch `ValueError`, so a malformed hook input could crash the hook with a stack trace; it now no-ops silently like other invalid-input paths.
- **pidash**: `pidash hooks install`/`uninstall` legacy-entry detection now matches by basename equality (`Path(token).name in LEGACY_HOOK_FILENAMES`) rather than substring. A user-written script whose filename happens to suffix one of the five legacy names (e.g. `backup-set-pidash-attention.py`) is no longer falsely flagged and removed.
- **bim**: `bim doc audit` walker now resolves each candidate path and skips entries (files or directories) whose target lies outside `<business_root>` after symlink resolution. Without this, a symlinked issuer subdir could make the audit traverse and report PDFs from anywhere on disk; the audit is documented as read-only against the Business folder and that boundary is now enforced.
- **bim**: `bim doc audit` now surfaces OCR/hash adapter failures as `ocr_check_failed` / `hash_check_failed` findings instead of silently treating the offending PDF as clean. Previously, an unreadable PDF, permission error, or buggy OCR adapter would produce no finding and bump the clean count, hiding the real failure mode. Read errors now flow into both stdout (✘ row) and JSON `pdf_findings` so the operator sees them.
- **bim**: `bim doc promote` now refreshes `state.db rule_matches` for triage proposals that originated from a rule-engine match. The pipeline records the winning rule_id on the `TriageProposal` (`applied_rule_id` field), and promote writes a fresh `last_matched_at` timestamp during the write path. Previously, only the auto-filing path refreshed rule freshness, so any rule whose matches consistently went to triage would falsely trigger the audit's 90-day staleness warning. Pre-existing proposals without `applied_rule_id` (default null) skip the refresh and behave as before.
- **bim**: `bim doc promote` now uses the triage proposal's `ingested-at` date for the `doc-date` fallback when a document has no extracted date (previously used `date.today()`, which made the same logical document yield different `doc-date` values when promoted on a different day from when it was triaged). Pipeline+promote consistency now holds for date-less documents too.
- **bim**: rule-engine conflict detection now flags two same-priority same-partial-ness rules pinning any shared field (was: only `issuer_slug`). Two rules pinning different `doc_type`, `doc_currency`, etc., are now correctly routed to triage with `rule_conflict: <id1> vs <id2>` instead of one silently winning.
- **bim**: `bim doc audit` walker now tolerates per-directory `OSError` (e.g. `PermissionError`) on `iterdir()` and continues with sibling directories, instead of aborting the entire audit on the first unreadable subtree. One misconfigured folder no longer blocks the rest of the report.
- **bim**: `bim doc audit` stdout no longer prints `0 low OCR confidence` when the OCR-quality reader cannot expose a confidence value for any walked PDF. The production pdfminer-based reader always returns `None` confidence, so the old line falsely implied the check ran successfully and found nothing. The reporter now emits `low OCR confidence: not assessed (reader does not expose confidence)` when no PDF was assessable, and the existing `{n} low OCR confidence` line whenever at least one PDF returned a real confidence value.
- **bim**: `bim doc audit` stdout no longer renders the `Watcher: not configured` stub row. The watcher heartbeat row appears only in spec §10's illustrative sample output, not in the normative §9 audit table that PRD 00037 imports, so emitting a stub line for it added noise. Sections now correspond 1:1 to §9; a watcher row will be reintroduced when the watcher heartbeat is wired up.

### Changed

- **pidash**: ``pidash`` is now a Click group. The TUI is still the default (``pidash`` with no args); to pass a project path explicitly, use ``pidash --project-path <path>`` or ``pidash tui <path>``. The previous positional ``pidash <path>`` form is no longer accepted.
- **bim**: `bim doc audit` JSON report adds a `non_clean_pdf_count` field so consumers have an exact partition with `clean_pdf_count` (`clean + non_clean == walked`). The audit's stdout is unchanged. Documentation now states explicitly that `pdf_findings` is one-entry-per-finding (a PDF with multiple findings appears multiple times sharing `pdf_path`), not one-entry-per-PDF, eliminating the previous doc/impl drift that PRD 00036 consumers might trip over.
- **bim**: `bim doc audit` "No conflicts" check now detects overlapping match clauses per spec §9, not only pinned-constant disagreement. Two enabled rules at the same priority are flagged whenever their `match` clauses are not statically provably disjoint (only `email_from_domain` literal-list disjointness is currently decidable; regex/substring clauses are conservatively treated as potentially overlapping). Disagreeing pinned `extract` values continue to be surfaced in the finding detail to help authors locate the conflict.
- **bim**: `Classifier.classify`/`classify_with_model`/`classify_with_pinned` now take a `SourceMetadata` dataclass instead of a `dict[str, object]` for `source_metadata`. The pipeline builds source metadata in one place (`Pipeline._build_source_metadata`) and feeds it to both the rule engine and the classifier, eliminating the previous parallel `_build_source_metadata` (dict) + `_build_rule_source_metadata` (dataclass) builders that could drift if a new metadata field was added to only one. Public CLI behaviour is unchanged.
- **bim**: triage proposals now carry the LLM-generated `summary` from extraction in their `zettel_preview.summary` field, and `bim doc promote` threads that summary into the promoted zettel body. Documents promoted from triage now match the ingest-path body shape (summary paragraph between the H1 and the `## OCR text` callout). Existing proposals without a `summary` field load unchanged (defaults to `None`).
- **bim**: `bim doc` zettels embed the source-file link in `file-path` frontmatter as `"[Open file](file://...)"` instead of an `[Open PDF]` link in the body (file-type-agnostic). The internal `DocumentZettelFrontmatter.file_path` attribute keeps a raw absolute path; the Markdown-link wrapping happens only at YAML serialisation time. Existing zettels are not rewritten.
- **bim**: zettel `ingested-at` frontmatter is now serialised with PyYAML's default space-separated form (`2026-05-04 14:30:22+02:00`) instead of T-separated. Round-trips via `datetime.fromisoformat` on Python 3.11+. v1 zettels written before this change (T-separated) still parse correctly; existing zettels are not rewritten.
- **bim**: default `classifier.primary_model` is now `qwen3:30b-a3b` (was `qwen2.5:7b-instruct`) and `classifier.fallback_model` is now `qwen3:14b` (was `qwen2.5:14b-instruct`). Users running with the default config will need `ollama pull qwen3:30b-a3b` (and `qwen3:14b` for the fallback) before `bim doc ingest` passes health check; users with an explicit `classifier.primary_model`/`fallback_model` override in their bim config are unaffected.

### Removed

- **build**: dropped Python 3.10 support. `requires-python` is now `>=3.11,<4.0`. The motivating constraint was the `ingested-at` `fromisoformat` round-trip in zettels, which on 3.10 required a custom YAML dumper to emit the T-separated form. With 3.11+ as the floor, the dumper is gone and the writer uses `yaml.safe_dump` directly. Users on 3.10 should upgrade to 3.11+ before installing 0.12+.

## [0.11.1] - 2026-05-10

### Added

- **bim**: doc rule engine v1 — deterministic per-issuer extraction before LLM fallback. New `bim doc rules` subcommand group (`list`, `validate`, `test`, `backtest`) for authoring and verifying rules. Existing `issuers.yml` files without `rules:` blocks load unchanged; full-rule matches set `extraction_method: rule:<id>:v<n>` and skip both Ollama calls, partial-rule matches set `extraction_method: rule+llm:<id>:v<n>` and reduce the prompt scope.
- **bim**: `bim doc ingest` shows a Rich spinner with per-stage labels (running OCR → classifying document → extracting fields) when stdout is a TTY; stays silent in batch/piped runs
- **bim**: `bim doc ingest` extractor now receives a `Hints:` block containing the original filename and email subject when known; the LLM uses these to ground field values when OCR text is noisy or numbers span line breaks (downloaded invoices often carry the invoice number as the filename)
- **bim**: `doc.ocr.extra_args` config field passes any extra `ocrmypdf` flags verbatim into both the redo and full-OCR branches (e.g. `--clean`, `--remove-background`, `--tesseract-pagesegmode 6`); the user owns flag correctness, the pipeline schema stays small

### Changed

- **bim**: doc zettel frontmatter and body switched to v1 shape: kebab-case keys (`doc-type`, `ingested-at`, `file-path`, ...), single `issuer` field (no more `issuer_slug`/`issuer_display`; the slug is in the canonical filename and `tags`), required `title` field, ISO 8601 datetime `ingested-at` with offset, source-file link in `file-path` frontmatter, optional LLM-generated summary paragraph, and per-issuer vault subfolder (`<vault>/<doc-subdir>/<issuer-slug>/<basename>.md`) mirroring the business-folder layout. `bim doc promote` preserves the triage proposal's `ingested-at`, so the same logical document driven through ingest vs promote now yields equivalent frontmatter (modulo `extraction-method`).
- **bim**: `bim doc ingest` extractor system prompt now spells out date/amount/currency formatting rules with examples (15.11.2024 → 2024-11-15, "1 234,56" → 1234.56, Kč → CZK), names the OCR-noise reconstruction expectation, and distinguishes invoice issue date from payment due date

### Removed

- **bim**: doc zettel body no longer renders `**Date:**` and `**Amount:**` metadata lines (information already lives in frontmatter)

### Fixed

- **bim**: `bim doc rules validate` now rejects `issuers: []` (and other falsy non-mapping shapes such as `issuers: ""` or `issuers: 0`) with a friendly `CommandResult` error, instead of silently collapsing them to "no issuers" via a `... or {}` short-circuit before the type guard ran
- **bim**: `doc ingest` now runs the LLM extractor whenever the classifier produced a `doc_type`, even when the issuer is unknown or classifier confidence is below `triage_threshold`. Triage proposals previously emitted nulls for `number`, `date`, `amount`, `currency`, and `title` because extraction was short-circuited; now the human reviewer sees the model's field-level output (full or partial) instead of a wall of nulls
- **bim**: `doc ingest` extractor now returns whatever fields it successfully coerced when raising `IncompleteExtraction` for missing/unparseable required fields; the pipeline surfaces this partial result in the triage proposal so coerced fields aren't discarded just because one required field is missing
- **bim**: `doc ingest` triage proposals now pre-fill the issuer slug with the classifier's slugified guess (when the LLM returned a slug not in the registry) so the human reviewer has a starting point instead of a blank field; `register_issuer` still defaults to `false` so registration requires explicit confirmation
- **bim**: expand `~` on every user-provided path in `doc.paths` (state_dir, vault_root, business_root, inbox_*, issuers_file, originals_dir) so `bim doc ingest` and `bim doc promote` no longer fail with `FileNotFoundError: '~/...'` when the config uses tilde paths
- **bim**: `doc ingest` and `doc promote` route missing-file errors through buvis console instead of Click's default `Usage: ... Error: ...` formatting
- **morph**: `html2md` and `deblank` route missing-path errors through buvis console
- **puc**: `strip` routes missing-file errors through buvis console
- **sysup**: `sysup nvim` no longer misreports successful mason installs as failures when `mason-tool-installer.nvim`'s `ensure_installed` mixes lspconfig names (`bashls`, `lua_ls`, `dockerls`, …) with mason package names. The probe now subscribes to `mason-registry`'s `package:install:failed` event before `MasonToolsUpdateSync` instead of querying `ensure_installed` entries by raw name, so the resolved mason package names are checked. Also strips iTerm2 OSC user-var escapes injected around the probe sentinels by shell integration

## [0.11.0] - 2026-05-06

### Added

- **bim**: doc subsystem v1 — ingest pipeline, triage workflow, issuer registry, OCR + LLM via Ollama/qwen2.5

### Changed

- **bim**: `bim doc ingest --strict` / `bim doc promote --strict` exits 1 on pipeline failure for scripting; default still exits 0
- **bim**: `bim doc ingest` and `bim doc promote` retry transient classifier/extractor failures up to `classifier.max_retries` times against `classifier.primary_model`, then fall back once to `classifier.fallback_model`. Semantic failures (JSON parse errors, missing/uncoercible fields from the classifier; field-derivation failures from the extractor) and timeouts now short-circuit to triage on the first attempt, no longer consuming the retry budget.
- **bim**: `DocPaths.business_root` must be under `Path.home()`; misconfigured paths now fail loudly at settings load instead of silently writing malformed `~<absolute>` strings into zettel frontmatter

## [0.10.0] - 2026-04-14

### Added

- **all tools**: `--update` flag force-checks PyPI and upgrades if a newer buvis-gems release is available; prints status or "already up to date"

## [0.9.0] - 2026-04-14

### Added

- **dot**: revert hunk or selected lines from diff pane with `r` (#78)

### Fixed

- **dot**: scroll diff pane to reveal content past the last hunk; add `ctrl+d`/`ctrl+u` half-page, `pagedown`/`pageup`, `g` (top), `G` (bottom) bindings (#77)
- **sysup**: capture mason probe output from stderr so per-tool OK/FAIL/INCONCLUSIVE states are reported again (#86)
- **sysup**: read mason ensure_installed from lazy.nvim plugin spec so per-tool install failures are detected (#87)

## [0.8.7] - 2026-04-14

### Changed

- **sysup**: `sysup nvim` mason step now fails when individual mason tools fail to install, reporting the missing tool names and a tail of `mason.log` instead of silently returning success

## [0.8.6] - 2026-04-12

### Added

- **dot**: persist diff pane scroll position when switching between files

### Fixed

- **dot**: scroll TUI panes to keep selected item visible during navigation
- **pidash**: scroll TUI panels and sidebar when content overflows viewport

## [0.8.5] - 2026-04-10

### Fixed

- **updater**: preserve installed extras when auto-updating in `pip` or `uv pip` venvs. Previously the upgrade command ran `pip install --upgrade buvis-gems` without extras, which silently removed previously installed extras (e.g. `dot`) on every upgrade and left tools like `dot` erroring with `dot TUI requires the 'dot' extra`

## [0.8.4] - 2026-04-10

### Fixed

- **sysup**: `sysup nvim` no longer hangs until the mason step timeout when `mason-tool-installer.nvim` is lazy-loaded. Force-loads mason plugins via `Lazy load` and uses the synchronous `MasonToolsUpdateSync` command so the subprocess exits as soon as the update completes

### Changed

- **sysup**: raise `sysup nvim` mason step timeout from 300s to 600s to accommodate slow package mirrors and cold proxy caches

## [0.8.3] - 2026-04-10

### Fixed

- **updater**: resolve the new binary path via `mise where pipx:buvis-gems` before re-exec, so upgrades on mise-managed installs no longer fail with `ENOENT`
- **updater**: exit cleanly instead of continuing after a successful upgrade when re-exec fails, avoiding cascading import errors from a partially-replaced venv

## [0.8.2] - 2026-04-10

### Changed

- **updater**: run auto-update check on every invocation (including `--version`, `--help`, and other eager callbacks) via a `click.Command.parse_args` patch scoped to `buvis_options` commands
- **updater**: silent operation — all update events now land in `~/.config/buvis/updater.json` (cache + rolling 100-entry log) instead of stderr, so tool output is never disturbed

## [0.8.1] - 2026-04-09

### Fixed

- **updater**: detect mise-managed pipx installations for auto-update
- **cli**: add missing CRITICAL log level to --log-level option

## [0.8.0] - 2026-04-09

### Added

- **gems**: auto-update check on CLI startup with installer detection and re-exec

## [0.7.0] - 2026-04-08

### Added

- **config**: `--feedback` flag on all CLI tools to open browser-based feedback form

### Fixed

- **dot**: only highlight selected file and update diff in the focused TUI pane
- **dot**: show GPG passphrase prompt before pull decryption in CLI mode

## [0.6.1] - 2026-04-08

### Fixed

- **sysup**: report nvim update progress per step instead of waiting until all steps finish
- **sysup**: include captured output in mason timeout error message

## [0.6.0] - 2026-04-07

### Added

- **sysup**: `nvim` command to update neovim plugins, mason tools, and treesitter parsers headlessly

## [0.5.2] - 2026-04-04

### Fixed

- **dot**: scroll file list panes to keep selected file visible when list overflows

## [0.5.1] - 2026-04-01

### Changed

- **pidash**: redesign state schema - rename description to issue, add cycle/consensus/action/reason/status/research fields, replace done_prds with BatchInfo, show resolution counts and batch progress

### Fixed

- **dot**: remove console import from commands layer (commands return CommandResult, CLI handles output)

## [0.5.0] - 2026-04-01

### Added

- **pidash**: multi-session mode - `pidash` (no args) watches `~/.pidash/sessions/` and shows all active sessions in sidebar + detail layout
- **pidash**: session sidebar with project name, phase badge, attention indicator, stale/done dimming
- **pidash**: keyboard navigation (up/down) to switch between sessions
- **pidash**: stale session detection (5min threshold, dimmed in sidebar)
- **pidash**: `--cleanup` flag to remove session files older than 24h
- **pidash**: auto-cleanup of stale session files on multi-session startup
- **pidash**: doubt-review phase in pipeline (CATCHUP → PLANNING → WORKING → REVIEWING → DOUBT → DONE)
- **pidash**: dedicated Doubts panel for doubt review findings
- **pidash**: render `[C{n}]` cycle tags in magenta, `[DOUBT]` tags in cyan
- **pidash**: render `[D{n}]` decision tags in task panel
- **dot**: `delete` command for removing files from tracking and disk (handles git-secret cleanup)
- **dot**: TUI mode - interactive terminal UI for dotfiles management (`dot` or `dot tui`)
- **dot**: TUI colored diff preview with auto-update on cursor movement
- **dot**: TUI commit modal, gitignore modal, delete confirmation dialog
- **dot**: TUI push/pull/refresh keybindings (p/P/r)
- **dot**: TUI space key as stage/unstage toggle
- **dot**: TUI hunk-level staging/unstaging (enter on focused hunk in diff pane)
- **dot**: TUI line-select mode for fine-grained staging (v to enter, space to toggle lines, enter to stage)
- **dot**: TUI file browser for discovering untracked files (b key, browse directories with tracking status)
- **dot**: TUI secrets panel for git-secret management (S key, reveal/hide/register/unregister)
- **dot**: TUI quick encrypt from any view (e key, register file with git-secret)
- **dot**: TUI configurable theme via `BUVIS_DOT_THEME` env var
- **dot**: TUI confirm-quit dialog on unsaved changes
- **dot**: TUI unpushed/unpulled arrow indicators in status bar

### Changed

- **dot**: `rm` command now keeps file on disk (uses `--cached`), use `delete` to remove from disk

### Fixed

- **pidash**: correct STATE_DIR from `.local/autopilot` to `dev/local/autopilot`
- **pidash**: escape brackets in task names to prevent Rich markup swallowing
- **dot**: GPG passphrase prompt in TUI instead of blocking on pinentry
- **dot**: auto-configure fetch refspec for bare repo remote tracking
- **dot**: fall back to `origin/<branch>` when `@{u}` upstream not set
- **dot**: refresh widgets immediately after list updates
- **dev**: `release local` reliably restores pyproject.toml after build
- **dev**: extract changelog from CHANGELOG.md for release notes
- **ci**: bump requests for CVE-2026-25645, ignore unfixable pygments CVE

## [0.4.0] - 2026-03-22

### Added

- **pidash**: new Textual TUI dashboard for monitoring autopilot PRD cycle status
- **pidash**: attention overlay when Claude needs permission approval
- **pidash**: animated braille spinner for active phases, task list with status markers
- **dot**: report unpushed/unpulled commits in status
- **dot**: skip push when nothing to push, hint GPG on pull failure
- **dev**: `release local` for .devN test builds
- **dev**: automate pyproject.toml tool wiring for new tools
- **ci**: split test matrix into lib + per-tool jobs

### Changed

- **zettel**: flatten fixers/upgrades directory structure
- **config**: consolidate paths, source, generators into fewer modules
- **pybase**: move DirTree from shared library to muc (sole consumer)
- **fctracker**, **pinger**: return CommandResult on error instead of raising exceptions
- **console**: exit with code 1 in panic()
- **deps**: replace bincode with rmp-serde, bump cache version to 4
- **deps**: upgrade textual 3.7→8.1, vite 8, marked 17

### Fixed

- **fren**: decode RFC 2047 encoded EML headers before slugifying
- **fren**: slug lowercase and eml timestamp format
- **bim**: run svelte-kit sync before vite build
- **dot**: replace pexpect with subprocess.run in shell interact
- **dot**: stage .gitignore in encrypt to prevent plaintext staging
- **dot**: push when upstream unknown, add supports dirs
- **dot**: add untracked files when adding a directory
- **pybase**: return actual stderr on failure, discard stderr on success

## [0.3.2] - 2026-02-24

### Added

- **dot**: staged/unstaged status, unstage command, commit positional arg

## [0.3.1] - 2026-02-24

### Added

- **dot**: encrypt and run commands

### Fixed

- **dot**: show deleted/new/renamed files in status, add missing pull steps

## [0.3.0] - 2026-02-24

### Added

- **fren**: file renamer toolkit — slug, directorize, flatten, normalize commands
- **morph**: file conversion toolkit — html2md and deblank commands
- **netscan**: network scanner tool
- **puc**: photo utility collection tool
- **sysup**: system update tool
- **vuc**: video utility collection tool
- **muc**: cover command for duplicate cover cleanup
- **dot**: pull, commit, push commands
- **ci**: SLSA build provenance attestation and SBOM generation

### Changed

- **console**: extract report_result, require_import, validate_path helpers

### Fixed

- **fren**: narrow broad except in EML slug fallback
- **morph**: avoid unlinking before restore in deblank
- **ci**: downgrade upload/download-artifact to v4

## [0.2.3] - 2026-02-20

### Fixed

- **jira**: populate environment field on issue creation

## [0.2.2] - 2026-02-20

### Fixed

- **bim**: sync description from zettel to linked jira issue
- **rust**: preserve reference section order using IndexMap

## [0.2.1] - 2026-02-20

### Fixed

- **config**: skip world-writable check on Windows

## [0.2.0] - 2026-02-20

Initial release.

### Added

- **pybase**: shared library — adapters, configuration, filesystem, formatting utilities
- **zettel**: subsystem with domain logic, Jira integration, and Rust extension (PyO3) for YAML scanning
- **bim**: BUVIS InfoMesh CLI — query engine with expression language, multiple output formats (table, json, jsonl, html, pdf, tui, kanban), web dashboard (SvelteKit), create/edit/show/delete/archive/format/import/sync commands
- **dot**: dotfiles manager with status and add commands
- **fctracker**: foreign currency account tracker
- **hello_world**: sample script template
- **muc**: music collection tools
- **outlookctl**: Outlook CLI
- **pinger**: ICMP ping utilities
- **readerctl**: Readwise Reader CLI
- **zseq**: Zettelsequence utilities
- **zettel**: metadata cache for fast filtered queries, recurrence parsing, expand directive, subclass instantiation
- **config**: Pydantic-based settings with Click option generation
- **ci**: GitHub Actions with test matrix, coverage, ruff lint, mypy, dep audit, GitHub releases

[Unreleased]: https://github.com/buvis/gems/compare/gems-v0.12.6...HEAD
[0.12.6]: https://github.com/buvis/gems/compare/gems-v0.12.5...gems-v0.12.6
[0.12.5]: https://github.com/buvis/gems/compare/gems-v0.12.4...gems-v0.12.5
[0.12.4]: https://github.com/buvis/gems/compare/gems-v0.12.3...gems-v0.12.4
[0.12.3]: https://github.com/buvis/gems/compare/gems-v0.12.2...gems-v0.12.3
[0.12.2]: https://github.com/buvis/gems/compare/gems-v0.12.1...gems-v0.12.2
[0.12.1]: https://github.com/buvis/gems/compare/gems-v0.12.0...gems-v0.12.1
[0.12.0]: https://github.com/buvis/gems/compare/gems-v0.11.1...gems-v0.12.0
[0.11.1]: https://github.com/buvis/gems/compare/gems-v0.11.0...gems-v0.11.1
[0.11.0]: https://github.com/buvis/gems/compare/gems-v0.10.0...gems-v0.11.0
[0.10.0]: https://github.com/buvis/gems/compare/gems-v0.9.0...gems-v0.10.0
[0.9.0]: https://github.com/buvis/gems/compare/gems-v0.8.7...gems-v0.9.0
[0.8.7]: https://github.com/buvis/gems/compare/gems-v0.8.6...gems-v0.8.7
[0.8.6]: https://github.com/buvis/gems/compare/gems-v0.8.5...gems-v0.8.6
[0.8.5]: https://github.com/buvis/gems/compare/gems-v0.8.4...gems-v0.8.5
[0.8.4]: https://github.com/buvis/gems/compare/gems-v0.8.3...gems-v0.8.4
[0.8.3]: https://github.com/buvis/gems/compare/gems-v0.8.2...gems-v0.8.3
[0.8.2]: https://github.com/buvis/gems/compare/gems-v0.8.1...gems-v0.8.2
[0.8.1]: https://github.com/buvis/gems/compare/gems-v0.8.0...gems-v0.8.1
[0.8.0]: https://github.com/buvis/gems/compare/gems-v0.7.0...gems-v0.8.0
[0.7.0]: https://github.com/buvis/gems/compare/gems-v0.6.1...gems-v0.7.0
[0.6.1]: https://github.com/buvis/gems/compare/gems-v0.6.0...gems-v0.6.1
[0.6.0]: https://github.com/buvis/gems/compare/gems-v0.5.2...gems-v0.6.0
[0.5.2]: https://github.com/buvis/gems/compare/gems-v0.5.1...gems-v0.5.2
[0.5.1]: https://github.com/buvis/gems/compare/gems-v0.5.0...gems-v0.5.1
[0.5.0]: https://github.com/buvis/gems/compare/gems-v0.4.0...gems-v0.5.0
[0.4.0]: https://github.com/buvis/gems/compare/gems-v0.3.2...gems-v0.4.0
[0.3.2]: https://github.com/buvis/gems/compare/gems-v0.3.1...gems-v0.3.2
[0.3.1]: https://github.com/buvis/gems/compare/gems-v0.3.0...gems-v0.3.1
[0.3.0]: https://github.com/buvis/gems/compare/gems-v0.2.3...gems-v0.3.0
[0.2.3]: https://github.com/buvis/gems/compare/gems-v0.2.2...gems-v0.2.3
[0.2.2]: https://github.com/buvis/gems/compare/gems-v0.2.1...gems-v0.2.2
[0.2.1]: https://github.com/buvis/gems/compare/gems-v0.2.0...gems-v0.2.1
[0.2.0]: https://github.com/buvis/gems/releases/tag/gems-v0.2.0

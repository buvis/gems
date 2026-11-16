# Fourth agoge walk: leftover verification

2026-11-16, branch `feature/config-local-layer-braid`, starting at `0d679585`.
Fetched origin first: clean tree, 86 ahead, remote tip `3c8a1671` authored by
Agent ran by Tomáš Bouška <tomas@buvis.net>.

## Coverage

- Issuers loading: all six command routes (ingest, promote, triage --approve,
  rules test/list/backtest) exercised with missing, malformed, empty,
  wrong-shape and missing-version files. Each prints exactly one console
  error, exits 1 and raises no unexpected exception. All 30 fail on old source.
- Dot TUI: real Textual terminal-mode driver under run_test captures a DEBUG
  record through `_apply_log_settings`; no probe text reaches terminal stderr.
  Headless mode intentionally forwards captured text and is unsuitable for
  this assertion. No production fix was needed.
- Resolver proves `BUVIS_PHOTO_DB__HOST` sets db.host; the extra underscore
  does not. Corrected all equivalent examples on the configuration page.
  Documentation regression failed before the edit and passes afterward.
- Held stubs 00143, 00146 and 00147 closed under the accepted decisions.
  Other held stubs were not changed.

## Fail-first audit

Archived `57aa9e14` source into a scratch directory, copied current tests and
pyproject.toml beside it, and ran pytest with that directory as cwd, rootdir
and configuration root. No PYTHONPATH override. Selected every changed test
function in `0d679585` by comparing Python ASTs, including modified existing
controls and the expanded issuer matrix. The already verified Rust regression
was excluded; no old-source Rust binary was substituted.

Final old-source result: **80 failed, 26 passed**. The failures are assertion
failures or the expected unhandled bad-input exceptions, not collection errors.
All selected new tests now distinguish the old behavior, except the backup
case whose fix predates this baseline (verified separately below).

Eight formerly vacuous new controls were tightened:

- console distinct-error warnings: also verify repeated-error deduplication;
- logging opt-in: prove DEBUG works before checking the default stays quiet;
- logger restoration: prove the handler actually emitted during the command;
- warning deduplication: prove DEBUG is active while checking one warning;
- git-secret setup: verify absence before creating .gitsecret;
- unstage existing file: verify refusal after removing the untracked file;
- valid dot repository: verify refusal after removing its repository directory;
- partial copy failure: verify failure when the remaining good input is removed.

The 26 old-source passes are 25 pre-existing compatibility cases modified for
fixture/message expectations, plus the new backup narrow-terminal test.
The backup soft-wrap fix is in `57aa9e14`, so passing there is expected.
Replacing only archived `backup/cli.py` with its `669b74b6` version makes that
test fail on the split path assertion (1 failed); current code passes.
No unrelated production change was invented to make a compatibility case fail.

## Gate

- Ruff check and format: clean (1,127 files).
- mypy: clean (577 source files; existing unused tomli-section note).
- cargo test: 37 passed.
- Sphinx: normal uv run --no-sync build and forced clean build both pass,
  with no warnings anywhere, including configuration.rst and tools/dot.rst.
- Full Python suite: 7,808 passed, 16 skipped, 1 xfailed (exit 0; JUnit confirms zero failures/errors).

## Blocker

Trudy/security lane remains unrun. Only the user can authorize it using
`/agoge:run-agoge --authorized <source>` or an Authorization line in the profile.
This closeout does not assert security-lane coverage.

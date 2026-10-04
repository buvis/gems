# zettel scanner: surface parse errors instead of dropping notes

<!-- requirements; migrated from PRD 00050 flat file -->

## Problem

When the zettel scanner hits a note it cannot parse, the note silently disappears from results and nothing is reported. `MarkdownZettelRepository` calls the scanner as `raw_list, _errors = load_filtered(...)` / `load_all(...)` and **discards `_errors`** (`src/lib/buvis/pybase/zettel/infrastructure/persistence/markdown_zettel_repository/markdown_zettel_repository.py:92,94`). The Rust scanner isolates a bad file into a returned `errors` vec (good) — but the caller throws it away, so a poisoned or malformed note vanishes from every query, TUI list, and API response with zero signal. Worse, the two backends disagree: the Python fallback path (`:97-110`) collects no errors and can raise out of `find_all` instead, so the same bad note behaves differently depending on whether the Rust wheel is present.

## Solution

Surface the dropped `_errors`: at minimum, warn once per scan (via the console adapter) listing the files that failed to parse, and/or return them in query metadata so interfaces can show "N notes could not be read." Align the Python fallback to collect per-file errors the same way the Rust path does, so behavior is backend-independent.

## Requirements

### Must have
- Scanner parse errors are no longer discarded: the repository surfaces them (warn-once via console and/or a structured field the caller can render).
- The Python fallback collects per-file parse errors instead of letting one bad note raise out of `find_all` — matching Rust's isolate-and-report semantics.
- A poisoned note produces a visible warning naming the file, and the remaining notes still load.
- Regression test (backend-agnostic, parametrized over Rust-present / fallback if feasible): a directory with one malformed note yields the good notes plus a reported error for the bad one.

### Nice to have
- Thread the error list into `bim query` / TUI / serve so the count is user-visible, not just logged.

## Success Criteria

- No note silently vanishes from a scan; the failure is visible.
- Rust and Python fallback agree on poisoned-note behavior; parity + zettel tests green.

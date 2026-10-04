# Decouple pybase from Click at import time

<!-- requirements; migrated from PRD 00052 flat file -->

## Problem

Importing `buvis.pybase.configuration` monkey-patches Click **globally at module import time**: `_install_parse_args_patch()` is called at module level (`src/lib/buvis/pybase/configuration/click_integration.py:179`), reassigning `click.Command.parse_args` / `click.Group.parse_args`. It is re-exported from the package `__init__` (`configuration/__init__.py:24`). This makes Click a hard dependency of every settings consumer and installs auto-update interception as a side effect of merely loading configuration. The all-interface goal means FastAPI/WebUI/TUI processes load settings too — and today they cannot without importing Click and triggering the update patch. The updater compounds it by emitting user-facing output through `click.echo` (9 sites: 5 in `updater/__init__.py`, 4 in `updater/executor.py`), bypassing the console adapter the rest of the repo mandates.

## Solution

Install the parse-args patch only when a Click CLI actually opts in — inside the `buvis_options` decorator — instead of at import time. Route updater output through the console adapter. Stop re-exporting Click glue from `configuration/__init__`. After this, importing `configuration` for `GlobalSettings` in a non-CLI process pulls no Click patching and no update machinery.

## Requirements

### Must have
- The global `click.Command.parse_args` / `click.Group.parse_args` patch is installed from within `buvis_options` (or first CLI construction), not at module import. Importing `buvis.pybase.configuration` has no side effect on Click.
- `--update` / `--version` behavior is unchanged for actual CLIs (all 16 tools still work, `tool sub --update` still intercepts).
- Updater user-facing output routes through the console adapter, not `click.echo` (leave the interactive re-exec semantics from 00047 intact).
- `configuration/__init__` no longer re-exports Click integration glue as part of its public surface (or exposes it lazily so importing settings doesn't import Click).
- Regression test: importing `buvis.pybase.configuration` (and constructing `GlobalSettings`) in a process that never builds a Click command does not patch `click.Command.parse_args` and does not import the updater.

### Nice to have
- A short note in AGENTS.md that the library must stay CLI-framework-agnostic (also covered by the guardrail edits).

## Success Criteria

- A headless (API/WebUI/TUI) process can load `GlobalSettings` without importing Click or the updater.
- All 16 CLIs behave identically to before. lib + tool tests green.

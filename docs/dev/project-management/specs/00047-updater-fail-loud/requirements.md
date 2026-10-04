# updater: fail loud on re-exec failure and slow upgrades

<!-- requirements; migrated from PRD 00047 flat file -->

## Problem

The auto-updater can silently swallow the user's command. After a successful upgrade it re-execs the original command; if the re-exec fails (PATH/venv moved), it logs only to `~/.config/buvis/updater.json` and then `sys.exit(0)` (`src/lib/buvis/pybase/updater/executor.py:140-147`). Because auto-update runs before every command via the parse-args patch (`configuration/click_integration.py:160-173`, gated by `settings.auto_update`), a scripted `bim doc ingest x.pdf` can exit 0 having ingested nothing and printed nothing — cron/scripts believe it worked. Separately, the upgrade subprocess has a hard `timeout=120` (`executor.py:55-62`) that can SIGKILL `uv tool upgrade` mid-run on a slow network, potentially leaving a half-mutated tool venv.

## Solution

On re-exec failure, print to stderr via the console adapter and exit non-zero (or fall through and run the original command in-process). Remove or substantially raise the 120s timeout on the interactive upgrade path so a slow-but-fine upgrade is not killed.

## Requirements

### Must have
- Re-exec failure results in a non-zero exit **and** a user-visible message via the console adapter (not just a JSON log line) — or falls through to run the original command in-process. Silent `sys.exit(0)` on failure is removed.
- The upgrade subprocess no longer has a 120s hard timeout on the interactive path (remove it, or raise it well beyond realistic upgrade time and document why).
- Regression test: a patched failing re-exec produces a non-zero exit and an error message; a success path is unchanged.

### Nice to have
- Route the remaining updater `click.echo`/`print` output through the console adapter (fuller fix lands in 00052; a light touch here is fine).

## Success Criteria

- No update path can exit 0 without having run the user's command.
- A slow upgrade is not truncated. lib tests green.

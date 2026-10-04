# pidash hooks: lock, fsync, and preserve order

<!-- requirements; migrated from PRD 00049 flat file -->

## Problem

pidash's autopilot state is written by hook processes that can run concurrently (multiple Claude Code sessions / parallel tool calls), and the writes are not coordinated:

- **Lost-update race.** `hooks/update_tasks.py:182-193` and `hooks/sync_agent_return.py:124-141` each do an unlocked read-modify-write of `state.json`. `write_json_atomic` (`hooks/session.py:67-87`) prevents a torn file but not interleaving: a `PostToolUse(TaskUpdate)` and a `PostToolUse(Agent)` firing concurrently can have B's write carry A's stale task status, so a completed task shows pending — and an autopilot relaunch from `state.json` can re-execute a finished task.
- **Tracked low-severity items to fold in:** #111 (`save_settings` should fsync before `os.replace`), #112 (hooks-install non-dict entries land at the end instead of preserving order), #113 (`hooks` subgroup missing `@click.pass_context`), #114 (`hooks_status` double-render via `console.info` after `report_result`).

## Solution

Add a `fcntl.flock` on a sidecar lock file around the whole load→mutate→replace sequence in the state-mutating hooks so concurrent writers serialize. Add fsync-before-replace to `save_settings` (#111). Fix the install ordering (#112) and the two low cosmetics (#113, #114). This clears the entire open pidash issue set in one session.

## Requirements

### Must have
- The four hooks that write `state.json` (`update_tasks`, `sync_agent_return`, `set_attention`, `clear_attention`) hold a `flock` on a sidecar lock file for the full read-modify-write; `write_json_atomic` stays as the atomic-replace primitive underneath. (`cleanup_session` writes only the per-session mirror file, not `state.json` — no lock needed.)
- `save_settings` fsyncs the tempfile before `os.replace` (#111) — reuse the shared `atomic_write` from 00041 where it fits.
- Hooks-install preserves the original order of existing hook-array entries, including non-dict entries (#112).
- `hooks` Click subgroup uses `@click.pass_context` (#113); the row-rendering loop duplicated between `hooks_status` and `_render_status_failure` is deduplicated into one helper, and #114 is closed as not-reproducible (grounded 2026-07-10: `report_result` never renders the rows, so there is no runtime double render).
- Regression tests: concurrent-writer test (two interleaved RMW cycles under the lock leave both updates intact); install-order test; the existing #111/#112 sketches in the issues.

### Nice to have
- Close #111–#114 on merge (#114 as not-reproducible, per above).
- Note in the commit/PR: the live hooks under `~/.claude/hooks/` are installed copies — re-run `pidash hooks install` after merge to deploy the fix to the running machinery.

## Success Criteria

- Concurrent hook writers cannot lose an update.
- pidash open issues #111–#114 closed; pidash tests green.

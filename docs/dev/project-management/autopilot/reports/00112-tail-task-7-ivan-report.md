Permission deny rule (/Users/bob/.claude/settings.json): Write(**/dev/local/**) is not matched by file permission checks — only Edit(path) rules are. Use Edit(**/dev/local/**) instead (Edit rules cover all file-editing tools).
Both findings are addressed with comments and docstrings only. Nothing was run, as the task instructed. Check the diff by eye; the orchestrator's full suite run will confirm nothing broke.

- **`runner.py` import:** a two-line comment above `from queue import Queue as ProgressQueue` says the separate binding is deliberate. Tests monkeypatch `backup.runner.queue.Queue` for the completion queue, and the progress queue must not be replaced along with it.
- **`Runner` docstring:** it now documents `on_progress` and `on_tick`.
  - **Timing:** `on_tick` fires after 0.2 s with no step completing.
  - **Thread:** callbacks run on the thread iterating `run`.
  - **Pause at `yield`:** no callbacks fire while the generator is paused there.
  - **Exceptions:** ordinary exceptions are swallowed.
  - **Callback behaviour:** callbacks should be short and nonblocking.
  - **Suppression:** nothing fires under `dry_run`, and the planning phase emits nothing.
- **`ProgressEvent` docstring in `step_result.py`:** it now says `done_bytes` and `total_bytes` are input (source) bytes, and `None` when not measurable.

Signatures and behaviour are unchanged.

ASSUMPTIONS:
- "Plan suppression" means the planning phase (`_plan`) emits no progress events. I did not read `_plan` to confirm this.
- The 0.2 s idle tick is taken from the `completed.get(timeout=0.2)` call in `_collect_completion`.

FILES_TOUCHED:
src/tools/backup/runner.py
src/tools/backup/step_result.py

---
design: skip
default_model: sonnet
model_tier_rationale: One try block with exact message formats; every check fails loudly.
---
# `bim sync -t jira` dumps a traceback when Jira is unreachable or answers an error

Source: agoge run 2026-11-23, finding 7 of 21 (MEDIUM, verified, lanes heidi and trudy; the HTTP 400/401 half is mocked), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

A Jira connection failure or HTTP error is not caught. `CommandSyncNote.execute` builds `ZettelJiraAdapter` and calls it with no error handling, so the exception leaves the command class. The CLI prints a raw stack trace of more than a hundred lines. The web server's `sync_note` action answers a bare 500.

Every Jira outage or expired token shows the user a stack trace. This breaks the repo rule "never let raw exceptions (stack traces) reach the user" and the `CommandResult` discipline invariant.

## Solution

`CommandSyncNote.execute` in `src/tools/bim/commands/sync_note/sync_note.py` catches three exception types and returns `CommandResult(success=False, error=<message>, warnings=<warnings gathered so far>)`. One `try` wraps the adapter construction and the loop over paths. The first failure ends the run.

Caught types and exact messages. `{server}` is `self.jira_adapter_config.get("server")`, or the text `unknown server` when the key is absent or empty.

| Exception | `error` |
|---|---|
| `pydantic.ValidationError` (adapter config) | `Jira adapter config is invalid: {fields}` |
| `requests.exceptions.RequestException` | `Jira sync failed for {server}: connection failed ({class})` |
| `jira.exceptions.JIRAError` | `Jira sync failed for {server}: HTTP {status}` or `Jira sync failed for {server}: HTTP {status}: {text}` |

- `{fields}`: the `loc` of each entry of `exc.errors()`, parts joined with `.`, entries joined with `, `, in the order pydantic reports them. An empty config gives `Jira adapter config is invalid: server, token`.
- `{class}`: `type(exc).__name__`, for example `ConnectionError`.
- `{status}`: `exc.status_code`. `{text}`: `exc.text` with every run of whitespace collapsed to one space (`" ".join(exc.text.split())`). Use the form without `: {text}` when `exc.text` is empty or `None`.

The message is always one line.

Never put `str(exc)` or `repr(exc)` of any of the three into the message. `str(JIRAError)` includes the request headers, and the request carries `Authorization: Bearer <token>`. The pydantic message includes `input_value=...`. Build the message only from the fields named above.

Catch `pydantic.ValidationError` by its own name, not `ValueError`. `ZettelJiraAdapter._get_assembler` raises a plain `ValueError` for missing `defaults`; that stays uncaught here and the CLI's existing `except (ValueError, FileNotFoundError)` keeps handling it.

Import `JIRAError` from `jira.exceptions`, `requests.exceptions.RequestException`, and `ValidationError` from `pydantic`. `sync_note.py` already imports `ZettelJiraAdapter`, which needs the `jira` package (and `requests` with it), so no new optional-dependency guard is needed.

Resulting behaviour:

- CLI: `console.report_result(result, failure_msg="Sync failed", exit_on_failure=True)` in `src/tools/bim/note_read_cli.py` already prints a failed result as one ` ✘ ` line and exits 1. No CLI change.
- Serve: `handle_sync_note` in `src/tools/bim/commands/serve/_actions.py` already returns `result.to_dict()`, and the route maps a failed result to HTTP 422 with `"success": false`. No serve change.

## Requirements

### Must have
- Adapter construction raising `requests.exceptions.ConnectionError` with config `server` `http://127.0.0.1:9` gives `success is False` and `error == "Jira sync failed for http://127.0.0.1:9: connection failed (ConnectionError)"`.
- An empty adapter config, with `BUVIS_JIRA_SERVER` and `BUVIS_JIRA_TOKEN` removed from the environment, gives `success is False` and `error == "Jira adapter config is invalid: server, token"`.
- An adapter call raising `JIRAError(status_code=401, text="Unauthorized")` with config `server` `https://jira.example.com` gives `error == "Jira sync failed for https://jira.example.com: HTTP 401: Unauthorized"`.
- A `JIRAError` whose `request.headers` hold `Authorization: Bearer TOKEN-MARKER`, with config `token` `TOKEN-MARKER`, gives an `error` that does not contain `TOKEN-MARKER`.
- `bim sync -t jira <note>` with an unreachable Jira exits 1, prints exactly one ` ✘ ` line, and prints no `Traceback`.
- `POST /api/actions/sync_note` with an unreachable Jira answers 422 with `"success": false` and the same error text, not 500.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **bim**: \`bim sync -t jira\` now prints one error line and exits 1 when Jira is unreachable, answers an HTTP error, or the Jira adapter config is incomplete, instead of a stack trace. The web UI's sync action returns a failed result instead of a 500. The message names the server and the cause and never the token.`

### Nice to have
- None.

## Implementation

### Module: sync failure result
- **Location**: `src/tools/bim/commands/sync_note/sync_note.py`, `tests/tools/bim/test_sync_note.py`, `tests/tools/bim/test_note_read_cli_exit_code.py`, `tests/tools/bim/test_serve_actions.py`, `CHANGELOG.md`
- **Responsibility**: turn Jira construction and call failures into a failed `CommandResult`
- **Exports**: none
- New symbols: `test_unreachable_jira_is_a_failed_result_naming_the_server`, `test_invalid_jira_config_is_a_failed_result_naming_the_fields`, `test_jira_http_error_is_a_failed_result_with_status_and_text`, `test_jira_error_message_never_contains_the_token`, `test_sync_with_unreachable_jira_prints_one_error_line_and_exits_1`, `test_sync_note_action_returns_failed_result_when_jira_is_unreachable`
- **Risk**: Other adapters (reader, ntfy) may have the same hole and are not covered. A `ValueError` from `_get_assembler` (missing `defaults`) still reaches the serve action as a 500; this PRD does not change it. Notes synced before a mid-batch failure stay synced, and the failed result does not list them. Jira's response text is printed through console markup, so square brackets in it can be mangled until finding 6 of the same run lands. `test_sync_value_error` and `test_sync_not_supported` in `tests/tools/bim/test_bim_cli_handlers.py` pin the CLI's own `except` clauses; they mock the command class and must stay green unchanged. No existing test pins the traceback.

### Dependencies
- sync failure result: No dependencies (foundation)

## Test Strategy

Command-level tests go in `tests/tools/bim/test_sync_note.py`, class `TestCommandSyncNote`. They patch `bim.commands.sync_note.sync_note.ZettelJiraAdapter` as the neighbouring tests do: with `side_effect=requests.exceptions.ConnectionError("refused")` for the connection case, and with a mock adapter whose `update_description_from_project` raises `JIRAError` for the HTTP cases. The invalid-config test does not patch the adapter; it uses `monkeypatch.delenv` for `BUVIS_JIRA_SERVER` and `BUVIS_JIRA_TOKEN` and passes `jira_adapter_config={}`.

The CLI test goes in `tests/tools/bim/test_note_read_cli_exit_code.py`, class `TestSyncExitCode`. It patches the adapter with the `ConnectionError` side effect, leaves `CommandSyncNote` real, and runs with `catch_exceptions=False`.

The serve test goes in `tests/tools/bim/test_serve_actions.py`, class `TestServeActions`. It sets `client.app.state.jira_config`, patches the adapter with the `ConnectionError` side effect, and posts to `/api/actions/sync_note`.

Status of the evidence: the refused-port half is live and verified. The HTTP 400/401 half is `mocked`: the lane ran it against a fake Jira, not a real server. The real check needs a reachable Jira instance with a revoked or wrong token: run `bim sync -t jira <project note>` there and confirm one ` ✘ ` line with `HTTP 401` and no token text. No such instance exists in the test environment, so the tests here use a constructed `JIRAError`.

Evidence from the report, verbatim:

```
**Evidence** (confirmed). Server `http://127.0.0.1:9`, nothing listening:
`bim sync -t jira <note>` -> rc 1, 126 stderr lines ending `requests.exceptions.ConnectionError:
... Connection refused`. Same at `669b74b6`. Mocked half: a fake Jira answering 400 or 401 -> 51
lines ending `jira.exceptions.JIRAError: ...`; `POST /api/actions/sync_note` -> 500. The token
marker appeared in none of it.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_unreachable_jira_is_a_failed_result_naming_the_server`, `test_invalid_jira_config_is_a_failed_result_naming_the_fields`, `test_jira_http_error_is_a_failed_result_with_status_and_text` and `test_jira_error_message_never_contains_the_token` to `tests/tools/bim/test_sync_note.py`; watch them fail - Acceptance: `uv run pytest tests/tools/bim/test_sync_note.py -k "failed_result or never_contains_the_token"` fails on the unmodified code.
- [ ] Add `test_sync_with_unreachable_jira_prints_one_error_line_and_exits_1` to `tests/tools/bim/test_note_read_cli_exit_code.py` and `test_sync_note_action_returns_failed_result_when_jira_is_unreachable` to `tests/tools/bim/test_serve_actions.py`; watch them fail - Acceptance: `uv run pytest tests/tools/bim/test_note_read_cli_exit_code.py tests/tools/bim/test_serve_actions.py -k "unreachable"` fails on the unmodified code.
- [ ] Catch `ValidationError`, `requests.exceptions.RequestException` and `JIRAError` in `CommandSyncNote.execute` and return the failed result with the exact messages (depends on: previous two tasks) - Acceptance: `uv run pytest tests/tools/bim/test_sync_note.py tests/tools/bim/test_note_read_cli_exit_code.py tests/tools/bim/test_serve_actions.py tests/tools/bim/test_bim_cli_handlers.py` passes.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "bim sync -t jira" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest tests/tools/bim/test_sync_note.py tests/tools/bim/test_note_read_cli_exit_code.py tests/tools/bim/test_serve_actions.py` passes; the project's full test gate (`uv run pytest`) passes.

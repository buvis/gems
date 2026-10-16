---
default_model: opus
model_tier_rationale: invented contracts that PRD 00096 consumes (attention state schema, fold and notify predicates, ntfy message shape, CLI group restructure); final text is given for the pure functions, but the orchestration and the test fixtures are designed, not transcribed
---

# sysup attention layer: end summary, persisted state, ntfy push, exit code, `sysup status`

Source: `docs/dev/project-management/intake/processed/00092-sysup-expiry-tracking/discovery.md` (PRD A of two; PRD 00096 adds the expiry registry on top of this layer)

## Overview

### Problem Statement
sysup prints one line per step as it goes (`_report_step`, `src/tools/sysup/cli.py:19-23`), keeps no state between runs, prints no end summary, sends nothing, and returns after reporting the last step (`src/tools/sysup/cli.py:99-102`), so a failed step exits 0.
A failure in the middle of a long run is lost unless the user scrolls back, and nothing outside the terminal ever hears of it.
`StepResult` is a plain class with `label`, `success`, `message` (`src/tools/sysup/step_result.py:4-8`): it cannot say which config entry produced a step, and it has no room for the amber "expiring" outcome PRD 00096 needs.
This PRD makes every not-ok outcome stick: one summary block after all output, one persisted entry per failing command until a complete clean run of that command, one ntfy push per run, exit 1 for failures of the current run, and `sysup status` to read the record back without running anything.

### Target Users
The solo operator running `sysup` by hand or from a scheduler, and PRD 00096, which feeds expiry checks into the same summary, state, push and exit code.

### Success Metrics
- `uv run pytest tests/tools/sysup/test_attention.py -q` passes: `test_failed_command_creates_one_entry_with_every_failure`, `test_success_after_failure_in_same_run_keeps_entry`, `test_complete_success_clears_entry`, `test_unchecked_names_keep_entries`, `test_red_entries_notify_every_run_amber_once`, `test_exit_code_counts_only_this_run`, `test_state_roundtrip_under_xdg_state_home`.
- `uv run pytest tests/lib/pybase/adapters/test_ntfy_adapter.py -q` passes: `test_request_url_body_and_basic_auth`, `test_non_latin1_title_is_rfc2047_encoded`, `test_http_error_returns_reason`, `test_success_returns_none`, `test_adapter_prints_nothing`, `test_malformed_url_returns_reason`.
- `uv run pytest tests/tools/sysup/test_sysup_cli.py -q` passes: `test_failed_step_prints_summary_writes_state_pushes_once_exits_1`, `test_filtered_run_keeps_and_labels_retained_entries_exits_0`, `test_status_prints_entries_and_exits_1_on_red`, `test_status_runs_nothing_writes_nothing`, `test_dry_run_and_list_write_no_state_send_nothing`, `test_group_options_before_subcommand_run_status_only`, `test_ntfy_not_configured_is_reported_not_fatal`, `test_malformed_ntfy_url_preserves_state_and_exit_code`.
- `uv run pytest -m sysup -q` passes; the only pre-existing tests that change are the three in `TestSysupCliShape` (`tests/tools/sysup/test_sysup_cli.py:16-32`), which assert that `cli` is not a group.
- `rg -c "exits 1" CHANGELOG.md` prints at least 1 (the accepted exit-code break is recorded under Changed).

## Functional Decomposition

### Capability: Step results carry a status and their command
Every step a run reports knows which config entry produced it and how bad it is.

#### Feature: Richer `StepResult`
- **Description**: `StepResult` becomes a frozen dataclass with `status`, `command` and `kind` fields, positional-compatible with every existing call site.
- **Inputs**: `label`, `success`, optional `message`, optional `status` (one of `ok`, `failed`, `expiring`, `expired`, `unknown`), optional `command`, optional `kind` (`command` or `item`).
- **Outputs**: an immutable record; `status` derives from `success` when not given.
- **Behavior**: final text of `src/tools/sysup/step_result.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["RED", "Kind", "Status", "StepResult"]

Status = Literal["ok", "failed", "expiring", "expired", "unknown"]
Kind = Literal["command", "item"]
RED: frozenset[str] = frozenset({"failed", "expired", "unknown"})


@dataclass(frozen=True)
class StepResult:
    """One reported step.

    ``status`` defaults from ``success`` (``ok`` / ``failed``); an expiry check
    (PRD 00096) passes ``expiring``, ``expired`` or ``unknown`` explicitly.
    ``command`` names the config entry that produced the step; the runner
    stamps it. ``kind`` tells a command entry from an expiry item.
    """

    label: str
    success: bool
    message: str = ""
    status: Status = "ok"
    command: str = ""
    kind: Kind = "command"

    def __post_init__(self) -> None:
        if not self.success and self.status == "ok":
            object.__setattr__(self, "status", "failed")
```

#### Feature: Runner stamps the command name
- **Description**: Every `StepResult` that leaves `Runner.run` carries `command=<entry name>`.
- **Inputs**: the `(name, command)` pairs `Runner.run` iterates (`src/tools/sysup/runner.py:36-51`).
- **Outputs**: the same results as today with `command` set.
- **Behavior**: every `StepResult(...)` the runner constructs itself (`_run_use` dry-run and failure paths, `_run_steps`, `_run_argv`, `src/tools/sysup/runner.py:67-135`) passes `command=name`; `_run_use` iterates the capability's results inside its `try` and yields `dataclasses.replace(step, command=name)` for each, so capability-owned labels such as `pip (3.12)` stay but fold under the entry name.

### Capability: Attention state
A durable record of what still needs the user, keyed by config entry name.

#### Feature: State file
- **Description**: Entries persist in `$XDG_STATE_HOME/sysup/attention.json` (fallback `~/.local/state/sysup/attention.json`), written atomically.
- **Inputs**: an entries mapping.
- **Outputs**: a JSON document `{"version": 1, "entries": {<name>: <entry>}}`; `read_state` returns the entries mapping, `{}` when the file is absent, unreadable or malformed.
- **Behavior**: same shape as `state_path` and `write_state` in `src/tools/klyreon/vault/state.py:20-24,39-43`, through `atomic_write_text` (`src/lib/buvis/pybase/filesystem/atomic_write.py:56-68`), `indent=2`, `sort_keys=True`, trailing newline, parents created. Entry shape, fixed here because PRD 00096 writes the same entries: `kind` (`command` or `item`), `status` (`failed`, `expiring`, `expired`, `unknown`), `details` (list of the not-ok messages of the last check), `first_seen` and `last_checked` (UTC ISO 8601 with seconds), `notified` (bool: a push carrying this entry succeeded at least once since the entry appeared).

#### Feature: Fold a run into the state
- **Description**: One entry per checked name: created or replaced when any of its results is not ok, removed when all are ok, untouched when the name was not checked this run.
- **Inputs**: current entries, the set of names checked this run, the run's `StepResult` list, `now`.
- **Outputs**: a new entries mapping (the input is not mutated).
- **Behavior**: final text of the pure functions in `src/tools/sysup/attention.py`:

```python
_RANK = {"expiring": 0, "unknown": 1, "expired": 2, "failed": 3}


def fold_results(
    entries: dict[str, Any], checked: set[str], results: list[StepResult], now: datetime
) -> dict[str, Any]:
    """Return a new entries mapping with every checked name updated.

    A checked name with no not-ok result loses its entry; one with any not-ok
    result gets one entry holding every not-ok message of this run, so a
    success after a failure inside the same run never clears the failure.
    Names not checked keep their entry untouched.
    """
    stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    names = checked | {r.command or r.label for r in results}
    folded = dict(entries)
    for name in names:
        bad = [r for r in results if (r.command or r.label) == name and r.status != "ok"]
        if not bad:
            folded.pop(name, None)
            continue
        previous = entries.get(name, {})
        worst = max(bad, key=lambda r: _RANK[r.status])
        folded[name] = {
            "kind": bad[0].kind,
            "status": worst.status,
            "details": [r.message or f"{r.label} {r.status}" for r in bad],
            "first_seen": previous.get("first_seen", stamp),
            "last_checked": stamp,
            "notified": bool(previous.get("notified", False)),
        }
    return folded


def to_notify(entries: dict[str, Any]) -> list[str]:
    """Names to push this run: every red entry, plus any entry never pushed."""
    return sorted(name for name, entry in entries.items() if entry["status"] in RED or not entry.get("notified"))


def mark_notified(entries: dict[str, Any], names: list[str]) -> dict[str, Any]:
    return {name: ({**entry, "notified": True} if name in names else entry) for name, entry in entries.items()}


def exit_code(results: list[StepResult]) -> int:
    """1 when a result of THIS run is red; retained entries never count."""
    return 1 if any(r.status in RED for r in results) else 0
```

The name fallback `r.command or r.label` keeps results that bypass the runner (the CLI tests patch `Runner.run` with bare `StepResult("brew", ...)` values) attached to a name. `to_notify` implements Q10: red entries push on every ordinary run, including retained ones; an amber entry pushes once (it is new, so `notified` is false) and never again while it stays amber; an entry that goes from red to amber was already pushed and stays quiet.

### Capability: Notification
Push the unresolved entries through ntfy, once per run, never fatally.

#### Feature: pybase ntfy adapter
- **Description**: A stdlib-only adapter in `src/lib/buvis/pybase/adapters/ntfy/ntfy.py` that returns a result and prints nothing.
- **Inputs**: `url`, `topic`, `title`, `message`, optional `credentials` (`user:password` for Basic auth), optional `timeout` (default 5 seconds).
- **Outputs**: `send_ntfy(...) -> str | None`: `None` on HTTP success, else the reason (`HTTP 403`, `URLError: ...`, `TimeoutError: ...`).
- **Behavior**: carries both fixes of `_header_safe` and `build_ntfy_request` in `~/.claude/hooks/notify.py:301-329`: a `User-Agent` that is not urllib's default (Cloudflare blocks `Python-urllib`), and a Title header encoded as an RFC 2047 encoded-word when it is not latin-1 or holds CR/LF. Final text:

```python
_USER_AGENT = "buvis-gems/ntfy"


def _header_safe(value: str) -> str:
    if "\r" not in value and "\n" not in value:
        try:
            value.encode("latin-1")
        except UnicodeEncodeError:
            pass
        else:
            return value
    token = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"=?UTF-8?B?{token}?="


def build_ntfy_request(url: str, topic: str, title: str, message: str, credentials: str = "") -> urllib.request.Request:
    headers = {"Title": _header_safe(title), "Tags": "computer", "User-Agent": _USER_AGENT}
    if credentials:
        token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return urllib.request.Request(f"{url.rstrip('/')}/{topic}", data=message.encode("utf-8"), headers=headers, method="POST")


def send_ntfy(url: str, topic: str, title: str, message: str, *, credentials: str = "", timeout: float = 5.0) -> str | None:
    """POST ``message`` to ``url/topic``; return None on success, else the reason."""
    try:
        request = build_ntfy_request(url, topic, title, message, credentials)
        with urllib.request.urlopen(request, timeout=timeout):
            return None
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"
```

Ruff S310 is silenced for this one file through `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml:165-174`, the way `src/lib/buvis/pybase/updater/checker.py` already is; no inline suppression marker. The module is imported directly (`from buvis.pybase.adapters.ntfy import send_ntfy`); `src/lib/buvis/pybase/adapters/__init__.py` is not touched.

#### Feature: ntfy configuration
- **Description**: `buvis-sysup.yaml` gains an `ntfy` section with `url`, `topic`, `credentials_file`; `NTFY_URL` and `NTFY_TOPIC` from the environment fill a missing url or topic.
- **Inputs**: the merged config layers `load_config` already builds (`src/tools/sysup/config.py:119-157`), including the `.local.yaml` twin.
- **Outputs**: `SysupConfig.ntfy: NtfySpec` with three optional string fields, all `None` by default.
- **Behavior**: `NtfySpec` is a frozen `extra="forbid"` model beside `WhenSpec`. Decided 2026-10-13 at create-prd: the discovery said "settings", but `SysupConfig` is `extra="forbid"` over the same `buvis-sysup.yaml` (`src/tools/sysup/config.py:64-70`), so any key the settings class would read from that file is rejected by `load_config`, and `ConfigResolver._merge_overrides` (`src/lib/buvis/pybase/configuration/resolver.py:190-211`) only copies keys that exist on the settings class anyway; one validated source wins. `credentials_file` is read with `expanduser()`; its stripped content is the Basic-auth `user:password`.

#### Feature: Push once per ordinary run
- **Description**: After folding, the CLI sends ONE message listing every name `to_notify` returns, then marks those entries notified.
- **Inputs**: the folded entries, the resolved url/topic/credentials.
- **Outputs**: title `sysup on <platform.node()>: <N> need attention`; body one line per name, `<status> <name>: <first detail>`; on success the pushed entries get `notified: true`.
- **Behavior**: nothing is sent when `to_notify` is empty. When url or topic is missing the summary gets `notification not sent: ntfy not configured` through `console.warning`; an unreadable credentials file gives `notification not sent: credentials file not readable: <path>`; a send failure gives `notification not sent: <reason>`. None of these change the exit code and none raise. Decided 2026-10-13 at create-prd: one aggregated message per run rather than one per entry; the "amber pushes once" rule is then about which lines the message carries, which the tests assert on the request bodies.

### Capability: CLI
`sysup` keeps its invocation shape and gains the summary, the exit code and `status`.

#### Feature: `sysup` becomes a group
- **Description**: `cli` is a `click.group(invoke_without_command=True)` keeping `--only`, `--tag`, `--list`, `--dry-run` as group options; bare `sysup [options]` behaves as today.
- **Inputs**: argv.
- **Outputs**: the current run for a bare invocation; the subcommand alone when one is named.
- **Behavior**: same arrangement as `src/tools/dot/cli.py:27-33`: the group callback returns at once when `ctx.invoked_subcommand` is not `None`, so `sysup --only brew status` runs `status` only and executes no command (the group options are parsed and ignored); `sysup status --only brew` is a Click usage error, as for every group. `@buvis_options(settings_class=SysupSettings)` stays on the group and still publishes `config_dir` / `config_path` in `ctx.obj` for the run and for subcommands.

#### Feature: End summary
- **Description**: After the last step line of an ordinary run, one block lists every unresolved entry, red and amber, including retained entries.
- **Inputs**: the folded entries, the `checked` set.
- **Outputs**: nothing when there are no entries; otherwise `console.nl()`, then `attention: <N> unresolved` via `console.warning`, then one line per entry in name order: `<name> (<status>): <details joined by "; ">`, through `console.failure` for red and `console.warning` for amber; a retained entry's parenthesis reads `(<status>, not rechecked this run)`.
- **Behavior**: the `checked` set is the names of the plan that ran (`{name for name, _ in plan}`); every other entry is retained. A run interrupted by `FatalError` panics as today and folds nothing (decided 2026-10-13 at create-prd: the panic itself is loud and already exits 1).

#### Feature: Exit code of an ordinary run
- **Description**: exit 1 when any result of this run is red; exit 0 otherwise, amber-only runs and retained red entries included.
- **Inputs**: the run's results.
- **Outputs**: `ctx.exit(1)` after the summary and the push, else a normal return.
- **Behavior**: `exit_code(results)` above. Accepted break (Q2): today a failed step exits 0.

#### Feature: `sysup status`
- **Description**: Prints the persisted entries and exits 1 when any is red; runs nothing, writes nothing, sends nothing.
- **Inputs**: `read_state()`.
- **Outputs**: `nothing needs attention` via `console.success` when empty; otherwise one line per entry, `<name> (<status>, checked <last_checked>): <details>`, red through `console.failure`, amber through `console.warning`; `ctx.exit(1)` when any entry is red.
- **Behavior**: does not call `load_config` and needs no config file.

#### Feature: Inspection modes touch nothing
- **Description**: `--list`, `--dry-run` and `status` fold no state, write no file and send no message.
- **Inputs**: the existing `list_plan` early return (`src/tools/sysup/cli.py:91-97`) and the `dry_run` flag.
- **Outputs**: today's output for `--list` and `--dry-run`.
- **Behavior**: the attention pipeline runs only on the ordinary path (`not dry_run`, no `--list`, no subcommand).

## Structural Decomposition

### Repository Structure

```
src/lib/buvis/pybase/adapters/ntfy/
├── __init__.py                     # Maps to: Notification (re-exports build_ntfy_request, send_ntfy)
└── ntfy.py                         # Maps to: pybase ntfy adapter
src/tools/sysup/
├── step_result.py                  # Maps to: Richer StepResult
├── runner.py                       # Maps to: Runner stamps the command name
├── config.py                       # Maps to: ntfy configuration (NtfySpec, SysupConfig.ntfy)
├── attention.py                    # NEW: Maps to: Attention state (state file, fold, notify decision, exit code)
└── cli.py                          # Maps to: CLI (group, summary, push, exit code, status)
tests/lib/pybase/adapters/test_ntfy_adapter.py   # NEW
tests/tools/sysup/
├── conftest.py                     # NEW: XDG_STATE_HOME and NTFY_* isolation for every sysup test
├── test_step_result.py             # NEW
├── test_attention.py               # NEW
├── test_runner.py                  # command stamping tests added
├── test_config.py                  # ntfy section tests added
└── test_sysup_cli.py               # TestSysupCliShape rewritten; attention tests added
docs/source/tools/sysup.rst         # Usage lines, Attention section, ntfy config
CHANGELOG.md                        # Added + Changed entries
pyproject.toml                      # per-file S310 ignore for the ntfy adapter
```

### Module: sysup.step_result
- **Maps to capability**: Step results carry a status and their command
- **Responsibility**: The immutable step record and the red-status set.
- **Exports**: `StepResult`, `Status`, `Kind`, `RED`
- New symbols: `Status`, `Kind`, `RED`, `expiring`, `expired`

### Module: sysup.runner
- **Maps to capability**: Step results carry a status and their command
- **Responsibility**: Unchanged execution; every yielded result is stamped with the entry name.
- **Exports**: `Runner` (signature unchanged)

### Module: sysup.config
- **Maps to capability**: Notification (ntfy configuration)
- **Responsibility**: `NtfySpec` and the `ntfy` field on `SysupConfig`; `load_config` unchanged otherwise.
- **Exports**: `NtfySpec` added to `__all__`
- New symbols: `NtfySpec`, `credentials_file`

### Module: sysup.attention
- **Maps to capability**: Attention state
- **Responsibility**: State path, read, atomic write, fold, notify decision, notified marking, exit code. Pure except for the file functions; no console output and no process exit. The invariant test's file list (`tests/tools/sysup/test_invariants.py:12-16`) gains this module.
- **Exports**: `state_path`, `read_state`, `write_state`, `fold_results`, `to_notify`, `mark_notified`, `exit_code`
- New symbols: `fold_results`, `to_notify`, `mark_notified`, `exit_code`, `attention.py`, `_RANK`, `first_seen`, `last_checked`

### Module: buvis.pybase.adapters.ntfy
- **Maps to capability**: Notification
- **Responsibility**: Build and send one ntfy POST with stdlib `urllib`; return the outcome; emit nothing (library stays interface-agnostic).
- **Exports**: `build_ntfy_request`, `send_ntfy`
- New symbols: `build_ntfy_request`, `send_ntfy`, `ntfy`, `_header_safe`, `NTFY_URL`, `NTFY_TOPIC`

### Module: sysup.cli
- **Maps to capability**: CLI, Notification (push once per run)
- **Responsibility**: Group with the existing options; the ordinary path collects results while reporting them, folds, prints the summary, pushes, writes state, sets the exit code; `status` renders the state.
- Final shape of the ordinary path's tail, replacing the report-and-return block at `src/tools/sysup/cli.py:99-102`:

```python
    results: list[StepResult] = []
    try:
        for step in Runner(cfg, dry_run=dry_run).run(plan):
            _report_step(step)
            results.append(step)
    except FatalError as exc:
        console.panic(str(exc))
        return
    if dry_run:
        return
    checked = {name for name, _ in plan}
    entries = fold_results(read_state(), checked, results, datetime.now(timezone.utc))
    _print_summary(entries, checked)
    entries = _notify(cfg, entries)
    write_state(entries)
    if exit_code(results):
        ctx.exit(1)
```

- **Exports**: `cli` (now a `click.Group`), subcommand `status`
- New symbols: `_print_summary`, `_notify`, `_entry_line`

### Module: tests
- **Maps to capability**: all
- **Responsibility**: `tests/tools/sysup/conftest.py` holds one autouse fixture that sets `XDG_STATE_HOME` to a `tmp_path` subdirectory and deletes `NTFY_URL` / `NTFY_TOPIC`, so no sysup test can touch the real state file or push. CLI tests patch `send_ntfy` where `sysup.cli` imports it and assert on the captured call, except the malformed-URL regression, which calls the real adapter with `urllib.request.urlopen` patched and asserts it is never reached. Adapter tests also patch `urlopen`. `TestSysupCliShape` becomes: `test_cli_is_a_group_with_status_only` (`isinstance(cli, click.Group)` and `set(cli.commands) == {"status"}`), `test_help_lists_filters` (unchanged assertions on the four options).
- **Exports**: none
- New symbols: `test_failed_command_creates_one_entry_with_every_failure`, `test_success_after_failure_in_same_run_keeps_entry`, `test_complete_success_clears_entry`, `test_unchecked_names_keep_entries`, `test_red_entries_notify_every_run_amber_once`, `test_exit_code_counts_only_this_run`, `test_state_roundtrip_under_xdg_state_home`, `test_request_url_body_and_basic_auth`, `test_non_latin1_title_is_rfc2047_encoded`, `test_http_error_returns_reason`, `test_success_returns_none`, `test_adapter_prints_nothing`, `test_failed_step_prints_summary_writes_state_pushes_once_exits_1`, `test_filtered_run_keeps_and_labels_retained_entries_exits_0`, `test_status_prints_entries_and_exits_1_on_red`, `test_status_runs_nothing_writes_nothing`, `test_dry_run_and_list_write_no_state_send_nothing`, `test_group_options_before_subcommand_run_status_only`, `test_ntfy_not_configured_is_reported_not_fatal`, `test_cli_is_a_group_with_status_only`, `test_help_lists_filters`, `test_status_derives_from_success`, `test_explicit_status_is_kept`, `test_results_carry_command_name`, `test_capability_results_are_restamped_with_command`, `test_ntfy_section_validates_and_defaults`, `test_ntfy_unknown_key_rejected`, `test_malformed_url_returns_reason`, `test_malformed_ntfy_url_preserves_state_and_exit_code`

### Module: docs and changelog
- **Maps to capability**: CLI (user-facing description)
- **Responsibility**: the Usage block of the sysup page (`docs/source/tools/sysup.rst:11-20`) gains a `sysup status` line.
  A new section titled Attention follows Configuration and describes the summary, the state file path, the exit-code rule, the ntfy config keys with the env fallback, and that the list, dry-run and status modes never write or push. `CHANGELOG.md` under `[Unreleased]`: `### Added` bullet `**sysup**: an end-of-run summary of everything unresolved, persisted in $XDG_STATE_HOME/sysup/attention.json until the failing command completes cleanly, pushed through ntfy (config `ntfy:` url/topic/credentials_file, env NTFY_URL/NTFY_TOPIC) once per run, and `sysup status` to read it back without running anything`; `### Changed` bullet `**sysup**: exits 1 when a step failed during the run (was 0); "expiring" outcomes and entries retained from earlier runs keep exit 0`.
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **sysup.step_result**: the record every other module reads.
- **buvis.pybase.adapters.ntfy**: self-contained stdlib adapter.
- **sysup.config**: `NtfySpec` as the `ntfy` field of `SysupConfig`, additive.

### Core Layer (Phase 1)
- **sysup.runner**: Depends on [sysup.step_result] (`command` field, `dataclasses.replace`).
- **sysup.attention**: Depends on [sysup.step_result] (`status`, `kind`, `RED`).

### Integration Layer (Phase 2)
- **sysup.cli**: Depends on [sysup.runner, sysup.attention, sysup.config, buvis.pybase.adapters.ntfy].
- **docs and changelog**: Depends on [sysup.cli].

## Implementation Phases

### Phase 0: Foundation
**Goal**: The record, the adapter and the config field exist with their own tests.

**Tasks**:
- [ ] Replace `src/tools/sysup/step_result.py` with the final text and add `tests/tools/sysup/test_step_result.py` (`test_status_derives_from_success`, `test_explicit_status_is_kept`, a frozen-instance test using `dataclasses.replace`) (no deps) - Acceptance: `uv run pytest tests/tools/sysup/test_step_result.py tests/tools/sysup/test_runner.py tests/tools/sysup/test_pip.py -q` passes (positional construction unchanged).
- [ ] Create `src/lib/buvis/pybase/adapters/ntfy/` with the final text, add the per-file S310 ignore to `pyproject.toml`, add `tests/lib/pybase/adapters/test_ntfy_adapter.py` patching `urllib.request.urlopen`: the six named tests, with `test_adapter_prints_nothing` asserting empty `capsys` output on both success and failure and `test_malformed_url_returns_reason` calling `send_ntfy` with `url="not-a-url"`, asserting a `ValueError: ...` return, empty output, and no `urlopen` call (no deps) - Acceptance: `uv run pytest tests/lib/pybase/adapters/test_ntfy_adapter.py -q` passes; `uv run ruff check src/lib/buvis/pybase/adapters/ntfy` clean; `rg -n "noqa" src/lib/buvis/pybase/adapters/ntfy` prints nothing.
- [ ] Add `NtfySpec` and the `ntfy` field of `SysupConfig` in `src/tools/sysup/config.py` with `test_ntfy_section_validates_and_defaults` and `test_ntfy_unknown_key_rejected` in `tests/tools/sysup/test_config.py` (no deps) - Acceptance: `uv run pytest tests/tools/sysup/test_config.py -q` passes.

**Exit Criteria**: the three Phase 0 test commands pass.

### Phase 1: Core
**Goal**: Results know their command; the state module folds, decides and persists.

**Tasks**:
- [ ] Stamp `command=name` on every result in `src/tools/sysup/runner.py`, wrapping capability results with `dataclasses.replace`; add `test_results_carry_command_name` (run entry) and `test_capability_results_are_restamped_with_command` (a `use:` entry whose capability yields label `pip (3.12)` comes out with `command == "pip"`) to `tests/tools/sysup/test_runner.py` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/sysup/test_runner.py -q` passes.
- [ ] Create `src/tools/sysup/attention.py` (state path, `read_state`, `write_state`, and the final-text functions) and `tests/tools/sysup/test_attention.py` with the seven named tests; `test_state_roundtrip_under_xdg_state_home` asserts the file lands under the fixture's `XDG_STATE_HOME`, that a malformed file reads as `{}`, and that a write leaves no `.tmp` sibling (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/sysup/test_attention.py tests/tools/sysup/test_invariants.py -q` passes with `attention.py` in the invariant file list.

**Exit Criteria**: `uv run pytest tests/tools/sysup -q` passes.

### Phase 2: Integration
**Goal**: The CLI prints, persists, pushes and exits as specified; docs describe it.

**Tasks**:
- [ ] Add `tests/tools/sysup/conftest.py` (autouse isolation fixture) and rewrite `TestSysupCliShape` in `tests/tools/sysup/test_sysup_cli.py` into `test_cli_is_a_group_with_status_only` and `test_help_lists_filters`; add the eight named CLI tests (depends on: Phase 1). Premise, re-checked at execution: `rg -c "    def test_" tests/tools/sysup/test_sysup_cli.py` prints 15 and the class `TestSysupCliShape` holds exactly three tests; otherwise stop and report. Acceptance: the count prints at least 22; `uv run pytest tests/tools/sysup/test_sysup_cli.py -q -k "group_with_status or failed_step_prints_summary" ` FAILS against the unchanged `cli.py` (output quoted in the task log).
- [ ] Turn `cli` into the group, add `_entry_line`, `_print_summary`, `_notify`, the ordinary-path tail above, and the `status` subcommand in `src/tools/sysup/cli.py` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/sysup/test_sysup_cli.py -q` passes; `test_failed_step_prints_summary_writes_state_pushes_once_exits_1` asserts, with `Runner.run` patched to yield one failed `StepResult("brew", False, "brew failed: boom")`, that the output holds `attention: 1 unresolved` and `brew (failed): brew failed: boom`, the state file holds the entry with `notified` true, `send_ntfy` was called once with a body containing `failed brew: brew failed: boom`, and the exit code is 1; `test_filtered_run_keeps_and_labels_retained_entries_exits_0` seeds a `helm` entry, runs `--only brew` with a passing brew, and asserts `helm (failed, not rechecked this run)` in the output, exit 0, the push body naming `helm`, and `sysup status` afterwards exiting 1; `test_malformed_ntfy_url_preserves_state_and_exit_code` uses the real adapter with `url="not-a-url"` and patched `urlopen`, parameterizes a current failed result (exit 1) and a successful filtered run with a retained unnotified entry (exit 0), and asserts a `notification not sent: ValueError: ...` warning, persisted `notified: false`, and no `urlopen` call.
- [ ] Update `docs/source/tools/sysup.rst` and `CHANGELOG.md` as specified in the docs module (depends on: previous task) - Acceptance: `rg -c "sysup status" docs/source/tools/sysup.rst` prints at least 2; `rg -c "exits 1" CHANGELOG.md` prints at least 1; `uv run sphinx-build -b html docs/source docs/build/html -q` exits 0.

**Exit Criteria**: `uv run pytest -m sysup -q` and `uv run pytest -m lib -q -k ntfy` green; `uv run mypy src/tools/sysup src/lib/buvis/pybase/adapters/ntfy` clean; `uv run ruff check src/tools/sysup src/lib/buvis/pybase/adapters/ntfy tests/tools/sysup tests/lib/pybase/adapters/test_ntfy_adapter.py` clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: one failing step in an ordinary run -> Expected: the step line as today, then the summary block, `attention.json` holding one `brew` entry, one `send_ntfy` call, exit 1; the next clean run of `brew` removes the entry, pushes nothing, exits 0.
- **Edge case**: a `pip-outdated` run with `numpy (3.12)` failing then `requests (3.12)` succeeding -> Expected: one `python-packages` entry whose `details` holds only the numpy message; exit 1; a later run where every package passes clears it.
- **Edge case**: `sysup --only brew` passing while a `helm` entry is retained -> Expected: `helm (failed, not rechecked this run)` in the summary, push body names `helm`, exit 0; `sysup status` exits 1.
- **Edge case**: an amber entry (seeded as `expiring`, `notified` false) across two runs with nothing else -> Expected: the first run's push body names it, the second run pushes nothing, both exit 0.
- **Edge case**: `sysup --only brew status` -> Expected: `status` output only, `Runner.run` never called, no state write.
- **Error case**: ntfy not configured and one entry exists -> Expected: `notification not sent: ntfy not configured` in the summary, state still written with `notified` false, exit code unchanged.
- **Error case**: a malformed ntfy URL fails during request construction -> Expected: warning with `ValueError: ...`, state still written with `notified` false, no network call or traceback, run exit code unchanged.
- **Error case**: `send_ntfy` returns `HTTP 403` -> Expected: `notification not sent: HTTP 403`, entries keep `notified` false so the next run retries, no traceback.
- **Error case**: `--dry-run` or `--list` with a seeded state file -> Expected: file bytes unchanged, `send_ntfy` not called.

## Risks

- **Exit-code break**: anything wrapping `sysup` and treating non-zero as fatal starts failing on failed steps. Mitigation: the Changed changelog entry; retained entries and amber never flip the code.
- **State written by one PRD, read by the next**: PRD 00096 writes `kind: item` entries with `expiring` / `expired` / `unknown`. Mitigation: the entry shape and `_RANK` already name those statuses; `to_notify` and `exit_code` key on `RED`, not on `failed`.
- **Tests touching the real state file or pushing for real**: Mitigation: the autouse conftest fixture; the adapter tests never open a socket (`urlopen` patched).
- **Click group option trap**: `sysup --only brew status` must not run anything. Mitigation: the early return on `ctx.invoked_subcommand` plus `test_group_options_before_subcommand_run_status_only`.
- **`buvis_options` on a group**: the decorator already serves groups (`dot`, `klyreon`); its `--update` interception on groups is exercised by those tools. Mitigation: `test_help_lists_filters` keeps the help contract.
- **Two ntfy implementations drift** (this adapter and `~/.claude/hooks/notify.py`): accepted; the hook is out of scope here.

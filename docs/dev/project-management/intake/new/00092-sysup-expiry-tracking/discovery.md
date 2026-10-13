# Discovery: sysup credential expiry tracking and attention-proof warnings

## Classification

Depth: comprehensive | Date: 2026-10-12

Source: `idea.md` beside this file.

Scored: clarity high, scope high (CLI, config, runner, new state, new
notifier, interactive flow), codebase impact high, complexity medium. Splits
into two sequenced PRDs (Q1).

## Problem

Credentials with a hard expiry are tracked nowhere. The agent's gh PAT
(`~/.config/gh-agent`) expires 2027-10-11; the first signal will be a failing
`gh` call inside a Seatbelt session that cannot fix it (no Keychain, refresh
needs a browser). The broader cause is that sysup cannot make anything stick:
it prints one line per step as it goes, keeps no state, has no end summary,
sends no notification, and exits 0 even when steps fail. A warning or failure
in the middle of a long run is lost unless the user scrolls back. If nothing
changes, the gh token dies silently in a year, and failed update steps keep
going unnoticed today.

## Requirements

### PRD A: attention layer (lands first)

- **A1 End summary**: after all step output, sysup prints one block listing
  every not-ok entry (failed step; in PRD B also expiring, expired, unknown
  items). Nothing is printed when everything is ok.
- **A2 Persisted state**: entries are written atomically
  (`pybase.filesystem.atomic_write`) to `$XDG_STATE_HOME/sysup/attention.json`
  (fallback `~/.local/state`). A run rewrites entries only for what it checked;
  a passing check clears its entry; entries for commands filtered out by
  `--only`/`--tag` stay (Q3).
- **A3 `sysup status`**: prints the persisted entries without running
  anything; exit 1 if any red entry exists.
- **A4 Notification**: a pybase ntfy adapter (stdlib `urllib`), settings for
  url, topic and credentials file, env fallback `NTFY_URL`/`NTFY_TOPIC`. Fires
  when an entry is new or its status worsens; red entries (failed, expired,
  unknown) fire on every run; amber (expiring) fires once (Q10). A send failure
  is reported in the summary, never fatal, never silent.
- **A5 Exit code**: exit 1 when any step failed or any item is expired or
  unknown; exit 0 otherwise, including amber-only runs (Q2).
- **A6 CLI group**: `sysup` becomes a Click group with
  `invoke_without_command=True`; bare `sysup` with `--only/--tag/--list/--dry-run`
  behaves as today (Q5).
- **A7 Dry run**: `--dry-run` writes no state and sends no notification.

### PRD B: expiry registry and guided refresh (depends on A)

- **B1 Registry**: an `expiry:` map in sysup config, layered like `commands`
  (bundled `default.yaml`, `buvis-sysup.yaml`, `.local` twin). Each item:
  `use:` (capability name), `with:` (validated by `load_config`),
  `warn_days` (default 30), `refresh:` (human steps text, plus commands, one of
  which may declare `stdin: secret`), `enabled`, `when` (same `WhenSpec`).
- **B2 Checked every run, before commands**: all applicable items run as a
  session-level pre-pass (like `prime`), one `StepResult` each, status ok /
  expiring in N days / expired / unknown. Required by B5, which must know item
  status before any command runs.
- **B3 Capability `gh-token-expiry`**: inputs `config_dir` (passed as
  `GH_CONFIG_DIR`) and `probe` (a `gh api` path needing private-repo access).
  Reads `Github-Authentication-Token-Expiration` from `gh api -i user`; a failed
  probe reports unknown with "grant broken" (Q6). Bundled item: `gh-agent` for
  `~/.config/gh-agent`, with the refresh steps from idea.md R4.
- **B4 Capability `x509-expiry`**: input is a PEM file path or `host:port`;
  reads `notAfter`. No bundled item (Q8).
- **B5 `needs:`**: command entries may declare `needs: [item]`; `load_config`
  rejects unknown item names. A command whose needed item is expired or unknown
  does not run and reports a failed step naming `sysup refresh <item>` (Q7).
- **B6 `sysup refresh <item>`**: refuses without a TTY. Prints the human steps,
  waits for Enter, reads the secret with `getpass`, runs the refresh commands
  (secret only on stdin of the one marked `stdin: secret`), re-checks the item,
  updates state. Never runs in a plain `sysup` pass (Q9).

### Nice to have

- `sysup status` shows days left for amber items, recomputed from the stored
  expiry date rather than the date of the last run.

### Out of scope

- Unattended refresh of any credential.
- Bundled items for the user's own `~/.config/gh` (unreadable under Seatbelt;
  add per machine in `.local` config), SSH certificates, API keys.
- Probing each PAT permission one by one.
- An ack command and an attention history log (Q3).
- Changes to `~/.claude/hooks/notify.py`.
- TUI, API or WebUI for sysup: it is a CLI-only tool today.

## Constraints

- No new runtime dependency (ntfy via stdlib; X.509 via an already-installed
  library, checked at design time).
- Existing `sysup` invocations keep working; the only accepted break is the
  exit code on failed steps (Q2).
- The secret never reaches argv, env, logs, state or notification (Q9).
- Library code stays interface-agnostic: the ntfy adapter returns a result and
  emits no output (AGENTS.md invariant).
- All state writes go through `atomic_write`.

## Codebase Context

- **Relevant code**: `src/tools/sysup/cli.py` (single `click.command`, reports
  each step via `console.success/failure`, no exit code on failure);
  `runner.py` (`Runner.run` yields `StepResult`, `_prime` handles session
  capabilities); `config.py` (`SysupConfig`, `SysupCommand`, `load_config`,
  `_validate_capabilities`); `capabilities/__init__.py` (`CAPABILITIES`
  registry, `Capability` protocol with `inputs` + `run`); `step_result.py`
  (plain class: label, success, message); `default.yaml`.
- **Conventions**: capabilities are code-owned and referenced by name, `with:`
  inputs validated against `capability.inputs` (00079); entries frozen Pydantic
  with `extra="forbid"`; lazy imports in the CLI handler; config via
  `--config`/`--config-dir` threaded into `load_config` (00084).
- **Integration points**: `StepResult` needs a status richer than
  `success: bool` (amber vs red); `SysupConfig` gains `expiry` and
  `SysupCommand` gains `needs`; `Runner` gains the item pre-pass and `needs`
  gating; `cli.py` becomes a group and owns summary, state, notify, exit code.
- **Similar implementations**: `src/tools/klyreon/vault/state.py`
  (`$XDG_STATE_HOME` path with fallback); `~/.claude/hooks/notify.py`
  `send_ntfy` / `build_ntfy_request` (ntfy request shape, Cloudflare User-Agent,
  RFC 2047 title, credentials file); `capabilities/sudo.py` (session-level
  capability outside the `use:` path).

## Approach

- **Chosen**: two sequenced PRDs. A turns sysup into a run that leaves a
  durable, pushed record of every failure. B adds expiry items as one more kind
  of check feeding the same record, plus a guided TTY refresh.
- **Why**: A fixes a live problem (failed steps vanish today) and gives B its
  output channel; each fits one autopilot session.
- **Rejected alternatives**:
  - One PRD: too much surface (CLI restructure, state, notifier, registry,
    interactive flow) for one batch.
  - Shelling out to `notify.py`: ties a published tool to a private hook path.
  - Expiry only, no grant probe: misses the 2026-10-12 failure mode.

## Success Criteria

- A run with one failing step prints it again in the end summary, writes it to
  `attention.json`, pushes one ntfy message, and exits 1; the next passing run
  clears the entry (tests with a fake step and a fake ntfy endpoint).
- `sysup status` prints persisted entries without running any step.
- An amber item pushes once across two runs; a red item pushes on both.
- `gh-token-expiry` maps a header date to ok / expiring / expired correctly
  around `warn_days`, and a failed probe to unknown (mocked `gh`).
- A command with `needs: [gh-agent]` does not run when `gh-agent` is expired
  and reports `sysup refresh gh-agent`.
- `sysup refresh gh-agent` without a TTY refuses; with a mocked TTY it passes
  the secret only via stdin (assert absent from argv and env).
- Every existing sysup test passes unchanged except those asserting exit 0 on
  a failed step.

## Risks

- **Exit-code break**: anything that runs sysup and treats non-zero as fatal
  starts failing on step failures. Mitigation: CHANGELOG entry under Changed.
- **ntfy settings missing in a plain shell**: `NTFY_*` live in Claude's
  settings.json env today. Mitigation: sysup settings for url/topic/credentials
  file; summary says "notification not sent: ntfy not configured".
- **Network blip turns the run red** via the grant probe (accepted, Q6).
  Mitigation: the unknown message names the cause (network vs grant).
- **Two ntfy implementations drift** (pybase adapter vs notify.py).
  Mitigation: note in notify.py's backlog; out of scope here.
- **Click group option trap**: `sysup --only x status` may parse oddly.
  Mitigation: explicit tests for both forms.
- **`needs:` has no real consumer** (Q7): tested only with config fixtures.

## Open Questions

- X.509 parsing: is `cryptography` already a transitive dependency, or does
  `x509-expiry` shell out to `openssl x509 -enddate`? Decide at design time
  under the no-new-dependency rule.
- SSH certificates are OpenSSH certs, not X.509 (`ssh-keygen -L` shows
  "Valid: ... to ..."); the idea listed them as a candidate. Out of scope here;
  confirm they stay out.
- Should item checks run under `--only`/`--tag` filtering, and under
  `--dry-run`? Default proposal: always run items (cheap, read-only) except
  under `--dry-run`.
- The grant probe target for `gh-agent`: which private buvis repo and which
  read call (for example `repos/buvis/gems/issues?per_page=1`).

## Discovery Log

### Q1: One PRD or split?
**Answer**: Split, sequenced. PRD A = attention layer (R3, R6: summary, persisted state, notifier, exit code for failed steps). PRD B = expiry registry, gh check, `sysup refresh` (R1, R2, R4, R5), built on A.

### Q2: Exit code when something needs attention?
**Answer**: Exit 1 when a step failed or an item is expired or unknown. "Expiring in N days" stays exit 0 but still appears in the summary and notification. Accepted break: today failed steps exit 0.

### Q3: When is an attention entry cleared?
**Answer**: The next passing check clears it. Each run rewrites entries only for what it checked; entries for steps filtered out by `--only`/`--tag` stay. `sysup refresh <item>` clears its item at once. No ack command, no history log.

### Q4: How does sysup send the push notification?
**Answer**: A small ntfy adapter in pybase (stdlib `urllib`, no new dependency), configured via sysup settings (url, topic, credentials file path) with `NTFY_URL`/`NTFY_TOPIC` env fallback. Must carry notify.py's known fixes (Cloudflare-safe User-Agent, RFC 2047 title encoding).

### Q5: CLI shape for `status` and `refresh`?
**Answer**: Click group with `invoke_without_command=True`. Bare `sysup [--only/--tag/--list/--dry-run]` runs as today; `sysup status` and `sysup refresh <item>` are subcommands. Tests must cover both forms and the group-option/subcommand parse trap.

### Q6: gh item checks expiry only, or the grant too?
**Answer**: Expiry plus one grant probe: one cheap authenticated call that needs real private-repo access (target set in the item's `with:`). Failure reports "unknown: grant broken". Accepted: a network blip turns the run red as unknown.

### Q7: Keep R5 although no step uses gh today?
**Answer**: Keep it as `needs: [item]` on command entries. The runner skips a step whose item is expired or unknown and reports `sysup refresh <item>` as a failed step. Recommendation was to defer; user chose to build the guard ahead of its first consumer.

### Q8: Which items ship in PRD B?
**Answer**: The agent gh token (bundled item for `~/.config/gh-agent`, capability parameterized by `GH_CONFIG_DIR`) plus a generic X.509 `notAfter` capability (file path or `host:port`). The cert capability ships without a bundled item; items are declared in user config.

### Q9: How does `sysup refresh` handle the pasted secret?
**Answer**: Hidden read via `getpass`, passed only on the stdin of the refresh command that declares `stdin: secret`. Never in argv, env, logs, state or notification; discarded right after use.

### Q10: How often does the notification fire while something stays not-ok?
**Answer**: On change, plus red each run. Push when an entry is new or its status worsens; failed, expired and unknown push on every run; "expiring in N days" pushes once and then stays in summary and status.

### Inferred (not asked)
- **Problem trigger**: a specific pain point (the 2026-10-12 gh grant incident and the untracked 2027-10-11 expiry), stated in idea.md.
- **Priority**: no rush for the expiry part (token valid until 2027-10-11); PRD A fixes a live problem (failed steps exit 0 and vanish).
- **Item pre-pass placement**: Q7 (`needs:`) forces items to be checked before any command, which settles idea.md R2's "prime or late-order" choice in favor of a pre-pass.
- **Interfaces**: sysup is CLI-only; the all-interface rule has no TUI/API/WebUI surface to extend here.


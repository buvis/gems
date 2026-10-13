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
  every unresolved not-ok entry (failed command; in PRD B also expiring,
  expired, unknown items), including retained entries not checked this run.
  Label retained entries "not rechecked this run". Nothing is printed when
  everything is ok.
- **A2 Persisted state**: entries are written atomically
  (`pybase.filesystem.atomic_write`) to `$XDG_STATE_HOME/sysup/attention.json`
  (fallback `~/.local/state`). Keep one entry per configured command name,
  containing all its failure details; clear it only after a complete
  successful execution of that command. A later successful result within a
  partially failed execution must not clear its failures. A run updates only
  commands and items it checked; entries for commands filtered out by
  `--only`/`--tag` stay. An expiry item's entry clears only when its check
  reports `ok` (Q3).
- **A3 `sysup status`**: prints the persisted entries without running
  anything; exit 1 if any red entry exists.
- **A4 Notification**: a pybase ntfy adapter (stdlib `urllib`), settings for
  url, topic and credentials file, env fallback `NTFY_URL`/`NTFY_TOPIC`. Fires
  when an entry is new or its status worsens; all unresolved red entries
  (failed, expired, unknown), including retained entries not rechecked, fire
  on every ordinary execution run; amber (expiring) fires once (Q10). A send
  failure is reported in the summary, never fatal, never silent.
- **A5 Exit code**: an ordinary execution run exits 1 when a command failed
  during that run or an item checked during that run is expired or unknown;
  exit 0 otherwise, including amber-only runs. Retained entries not rechecked
  remain visible but do not affect that run's exit code; `status` uses all
  persisted entries as specified in A3 (Q2).
- **A6 CLI group**: `sysup` becomes a Click group with
  `invoke_without_command=True`; bare `sysup` with `--only/--tag/--list/--dry-run`
  behaves as today (Q5).
- **A7 Inspection modes**: `--list`, `--dry-run`, and `status` execute no
  commands or expiry probes, write no state, and send no notifications.
  Listing and dry-run output continue to describe the plan; `status` reads
  persisted entries only.

### PRD B: expiry registry and guided refresh (depends on A)

- **B1 Registry**: an `expiry:` map in sysup config, layered like `commands`
  (bundled `default.yaml`, `buvis-sysup.yaml`, `.local` twin). Each item:
  `use:` (capability name), `with:` (validated by `load_config`),
  `warn_days` (default 30), `refresh:` (human steps text, plus commands, one of
  which may declare `stdin: secret`), `enabled`, `when` (same `WhenSpec`).
- **B2 Checked every execution run, before commands**: all applicable items
  run as a session-level pre-pass (like `prime`), including under `--only` and
  `--tag`; command filters do not filter items. Each item produces one
  `StepResult`, status ok / expiring in N days / expired / unknown. Inspection
  modes in A7 do not run this pre-pass. Required by B5, which must know item
  status before any command runs.
- **B3 Capability `gh-token-expiry`**: inputs `config_dir` (passed as
  `GH_CONFIG_DIR`) and `probe` (a `gh api` path needing private-repo access).
  Reads `Github-Authentication-Token-Expiration` from `gh api -i user`; a failed
  probe reports unknown with "grant broken" (Q6). Enabling an item requires
  an explicitly configured probe targeting a private repository; a public
  repository read does not establish the required grant. Bundled item:
  `gh-agent` for `~/.config/gh-agent`, with the refresh steps from idea.md R4,
  ships as a disabled template. Users supply their private probe and set
  `enabled: true` in local configuration; no personal probe target is bundled.
- **B4 Capability `x509-expiry`**: input is a PEM file path or `host:port`;
  reads `notAfter`. Provided through an optional certificate extra with an
  explicitly declared parser dependency; core sysup and gh tracking must work
  without that extra. No bundled item (Q8).
- **B5 `needs:`**: command entries may declare `needs: [item]`; `load_config`
  rejects unknown item names. A command whose needed item is expired or unknown
  does not run and reports a failed step naming `sysup refresh <item>` (Q7).
- **B6 `sysup refresh <item>`**: refuses without a TTY. Prints the human steps,
  waits for Enter, and runs the refresh commands. Read a secret with `getpass`
  only when a command declares `stdin: secret`, passing it only on that
  command's stdin; otherwise omit the secret prompt. Re-check the item and
  update state from the observed result: only `ok` clears its entry; expiring,
  expired, and unknown remain as attention entries. Refresh itself is not
  evidence of recovery. Never runs in a plain `sysup` pass (Q3, Q9).

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

- No new core runtime dependency; ntfy uses the stdlib. X.509 may add an
  explicitly declared parser dependency through an optional certificate
  extra, rather than relying on a development or incidental transitive
  dependency. Select the parser and extra name at design time.
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
- **Packaging**: `pyproject.toml` defines core and optional dependencies;
  `cryptography` is not declared among core dependencies. Certificate parser
  availability must be established through the optional extra.
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
  of that command clears the entry (tests with a fake step and a fake ntfy
  endpoint).
- A command emitting failure followed by success retains a single command
  attention entry with its failure details and exits 1; only a subsequent
  complete successful execution clears it.
- A successful filtered run retains excluded commands' failures, labels them
  "not rechecked this run" in the summary, repeats their red notifications,
  and exits 0 when its current checks have no red outcomes; `status` still
  exits 1 for the retained red entries.
- `sysup status` prints persisted entries without running any step or probe;
  `--list`, `--dry-run`, and `status` write no state and send no notification.
  Neither `--list` nor `--dry-run` executes commands or expiry probes.
- Ordinary runs under `--only` or `--tag` still check every applicable expiry
  item before executing selected commands.
- An amber item pushes once across two runs; a red item pushes on both.
- `gh-token-expiry` maps a header date to ok / expiring / expired correctly
  around `warn_days`, and denial of the configured private-repository probe
  to unknown (mocked `gh`).
- The bundled `gh-agent` template is disabled and performs no probes until
  enabled locally; enabling it without a configured private probe is rejected.
- A core-only installation supports ordinary sysup runs and gh tracking
  without the certificate extra; installing the extra supplies the declared
  parser and enables `notAfter` checks for PEM files and TLS endpoints.
- A command with `needs: [gh-agent]` does not run when `gh-agent` is expired
  and reports `sysup refresh gh-agent`.
- `sysup refresh gh-agent` without a TTY refuses; with a mocked TTY it passes
  the secret only via stdin (assert absent from argv and env).
- A refresh procedure without `stdin: secret` never requests a secret.
- Refresh clears attention only after an `ok` recheck; expiring, expired, and
  unknown rechecks update the entry without removing it.
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
- **Tracking remains disabled until configured**: the bundled `gh-agent`
  template cannot warn before local setup. Mitigation: document both the
  private probe configuration and explicit enable step.

## Open Questions

- X.509 packaging: select the parser dependency and certificate extra name
  at design time; declare the dependency explicitly in that extra and keep
  core-only sysup usable without it.
- SSH certificates are OpenSSH certs, not X.509 (`ssh-keygen -L` shows
  "Valid: ... to ..."); the idea listed them as a candidate. Out of scope here;
  confirm they stay out.

## Discovery Log

### Q1: One PRD or split?
**Answer**: Split, sequenced. PRD A = attention layer (R3, R6: summary, persisted state, notifier, exit code for failed steps). PRD B = expiry registry, gh check, `sysup refresh` (R1, R2, R4, R5), built on A.

### Q2: Exit code when something needs attention?
**Answer**: Exit 1 when a command failed during the current execution run or an item checked during that run is expired or unknown. "Expiring in N days" stays exit 0 but still appears in the summary and notification. Retained entries not rechecked remain visible and keep their notification behavior but do not affect the ordinary run's exit code; `status` exits 1 for any persisted red entry. Accepted break: today failed steps exit 0.

### Q3: When is an attention entry cleared?
**Answer**: One entry per configured command retains all its failure details until a complete successful execution of that command; success after a failure within the same run does not clear it. Each run updates only commands and items it checked; entries for commands filtered out by `--only`/`--tag` stay. An expiry item clears only when its check reports `ok`, including the recheck after `sysup refresh <item>`; expiring, expired, or unknown rechecks update the entry instead. No ack command, no history log.

### Q4: How does sysup send the push notification?
**Answer**: A small ntfy adapter in pybase (stdlib `urllib`, no new dependency), configured via sysup settings (url, topic, credentials file path) with `NTFY_URL`/`NTFY_TOPIC` env fallback. Must carry notify.py's known fixes (Cloudflare-safe User-Agent, RFC 2047 title encoding).

### Q5: CLI shape for `status` and `refresh`?
**Answer**: Click group with `invoke_without_command=True`. Bare `sysup [--only/--tag/--list/--dry-run]` runs as today; `sysup status` and `sysup refresh <item>` are subcommands. Tests must cover both forms and the group-option/subcommand parse trap.

### Q6: gh item checks expiry only, or the grant too?
**Answer**: Expiry plus one grant probe: one cheap authenticated call that needs real private-repo access (target set locally in the item's `with:` before enabling it). A public-repository read does not establish this grant; no personal probe target is bundled. Failure reports "unknown: grant broken". Accepted: a network blip turns the run red as unknown.

### Q7: Keep R5 although no step uses gh today?
**Answer**: Keep it as `needs: [item]` on command entries. The runner skips a step whose item is expired or unknown and reports `sysup refresh <item>` as a failed step. Recommendation was to defer; user chose to build the guard ahead of its first consumer.

### Q8: Which items ship in PRD B?
**Answer**: A disabled bundled `gh-agent` template for `~/.config/gh-agent` (capability parameterized by `GH_CONFIG_DIR`); users supply their private probe and explicitly enable it locally. Also a generic X.509 `notAfter` capability (file path or `host:port`) through an optional certificate extra with an explicitly declared parser dependency. The cert capability ships without a bundled item; items are declared in user config.

### Q9: How does `sysup refresh` handle the pasted secret?
**Answer**: Only a refresh command declaring `stdin: secret` triggers a hidden read via `getpass`; the secret is passed only on that command's stdin. Procedures without that declaration do not prompt for a secret. Never in argv, env, logs, state or notification; discarded right after use.

### Q10: How often does the notification fire while something stays not-ok?
**Answer**: On change, plus red each ordinary execution run. Push when an entry is new or its status worsens; all unresolved failed, expired and unknown entries push on every execution run, including retained entries not rechecked; "expiring in N days" pushes once and then stays in summary and status. Inspection modes never notify.

### Q11: Do filters or inspection modes run expiry checks?
**Answer**: All applicable expiry items are checked before commands on every ordinary execution run, including runs filtered by `--only` or `--tag`. `--list`, `--dry-run`, and `status` perform no commands or expiry probes, write no state, and send no notifications.

### Review decisions (2026-10-13)
All eight findings were accepted: command-level clearing (A2/Q3), recheck-based refresh clearing (B6/Q3), a locally configured private probe (B3/Q6), conditional secret prompting (B6/Q9), an optional certificate parser dependency (B4/Q8), retained-entry visibility with current-check exit codes (A1/A4/A5/Q2/Q10), execution-only expiry checks (A7/B2/Q11), and a disabled bundled template (B3/Q8). No findings were disputed or deferred.

### Inferred (not asked)
- **Problem trigger**: a specific pain point (the 2026-10-12 gh grant incident and the untracked 2027-10-11 expiry), stated in idea.md.
- **Priority**: no rush for the expiry part (token valid until 2027-10-11); PRD A fixes a live problem (failed steps exit 0 and vanish).
- **Item pre-pass placement**: Q7 (`needs:`) forces items to be checked before any command, which settles idea.md R2's "prime or late-order" choice in favor of a pre-pass.
- **Interfaces**: sysup is CLI-only; the all-interface rule has no TUI/API/WebUI surface to extend here.


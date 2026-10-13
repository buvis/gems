# sysup: track credential expiry and guide refreshes without losing the warning

Status: processed, specced as PRD 00092 (attention layer) and PRD 00096 (expiry registry and guided refresh). Recorded 2026-10-12.

## Problem

The agent's GitHub token is the first of a class. It is a fine-grained PAT in
`~/.config/gh-agent/hosts.yml`, picked up by `~/bin/run-agent` through
`GH_CONFIG_DIR`, and it expires on 2027-10-11 (the API reports it in the
`Github-Authentication-Token-Expiration` header of `gh api -i user`). Nothing
tracks that date. The first signal will be a failing `gh` call months from
now, inside a session that cannot fix it: the Keychain is unreachable under
the Seatbelt profile and the refresh needs a browser.

More items share the shape: a hard expiry, a check that code can run, and a
refresh that needs a human (create a token, approve a login, paste a secret).
Candidates: the user's own gh token, SSH certificates, TLS certificates, API
keys with a known lifetime, backup provider keys.

sysup is the natural home, since it is the recurring maintenance run. But
sysup today prints one line per step as it goes (`cli.py:21-23`), keeps no
state between runs, has no end-of-run summary and sends no notification. A
warning printed halfway through a long run is easy to miss, and the user
cannot be expected to scroll back and re-read everything.

## Idea (from the user)

Treat expiry as a common sysup concern, not a one-off for gh. A registry of
expiring items, each with a way to read its expiry and a refresh procedure.
sysup checks them on every run and warns ahead of time. Refreshes need user
interaction, so they are guided procedures, never unattended steps. The design
must assume sysup runs on its own and that a warning in the middle of its
output may go unseen.

## Requirements

1. **R1 Registry**: expiring items are declared in sysup config and layer like
   `commands` (bundled default, `buvis-sysup.yaml`, `.local` twin). Each item
   names a code-owned capability that reads its expiry (first one: the agent gh
   token via the expiration header under the item's `GH_CONFIG_DIR`), a warning
   threshold (default 30 days), and its refresh procedure: the human steps and
   the commands sysup can run for them.
2. **R2 Checked every run**: every run evaluates all items, as a session-level
   capability like `prime` or a late-order command. Per item the outcome is ok,
   expiring in N days, expired, or unknown (the check itself failed).
3. **R3 Attention-proof**: anything not ok is repeated in a summary block after
   all other output, persisted (for example `$XDG_STATE_HOME/sysup/attention`)
   so `sysup status` and the next run show it again until resolved, and pushed
   through the configured notifier (ntfy is already set up on this machine via
   `NTFY_URL` / `NTFY_TOPIC`). A missed scroll must not lose the warning.
4. **R4 Guided refresh**: `sysup refresh <item>` runs the procedure on a TTY:
   prints the human steps (for the gh item: create a fine-grained PAT, owner
   `buvis`, repository access All repositories, permissions Pull requests RW,
   Issues RW, Actions R, Commit statuses R, Contents R, Metadata R, one-year
   expiry), waits, reads the secret with input hidden, runs the commands
   (`GH_CONFIG_DIR=~/.config/gh-agent gh auth login --with-token
   --insecure-storage`), re-checks the expiry and clears the attention entry.
   It never runs inside an unattended `sysup` pass; the existing
   `interactive: true` semantics apply.
5. **R5 Fail loud when expired**: a step that depends on an expired item
   reports the refresh command instead of running unauthenticated or printing
   a bare tool error.
6. **R6 Same mechanism for failed steps**: a failed step mid-run has the same
   visibility problem, so the summary, state and notification of R3 cover
   failed steps too, not only expiries.
7. **R7 sysup conventions**: capability referenced by name from config,
   `with:` inputs validated by `load_config`, one `StepResult` per reported
   check, as established by 00079 (configurable updaters).

## Open questions

- Exit code: does "expiring soon" leave the run green and only "expired" or
  "unknown" turn it red?
- Where the attention state lives, and whether `sysup refresh` is the only
  thing that clears an entry or a passing re-check clears it too.
- Notifier: reuse the ntfy delivery the Claude hooks already use
  (`~/.claude/hooks/notify.py`), or a pybase notifier adapter that other gems
  can share?
- Should the gh item also verify the token's grant (the 2026-10-12 incident:
  a token whose repository access stayed "Public repositories (read-only)"
  authenticates but cannot do anything), or only its expiry?

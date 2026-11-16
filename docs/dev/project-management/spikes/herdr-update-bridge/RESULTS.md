# Bridge experiment results

2026-11-15. Disposable prototype only; no production implementation.

## Run

`mise exec -- bun docs/dev/project-management/spikes/herdr-update-bridge/probe.mjs`

The harness loads the exact mod source with mocked documented Herdr APIs.
It passes check-mode silence, malformed-command rejection, matching fresh
nonce, stale response rejection and simulated loaded-instance replacement.

The actual installed Herdr 0.1.16 also reports `check passed` for this mod with
HERDR_APP_HOME set to a temporary directory. Native checking fell back from
launchd submission to in-process execution. Optional gpui-shell storage creation
was denied by the environment; no elevated retry or bypass was attempted.

## ASSUMPTIONS

- The consumer generates a never-reused nonce for each bounded probe.
- A loaded mod can own one shared-state response key; the consumer does not
  modify Herdr's shared.json directly.
- The bridge only samples update state. Herdr remains responsible for update
  execution; sysup remains responsible for deciding whether to request actions.
- A missing/unloaded bridge is an unavailable observation source, never success.

## Native outcome

Approved request `d28570053c8e9b932b5f92e396967d2b` completed successfully on
2026-11-15 with Herdr 0.1.16 and hc 0.1.21 in isolated signed bundle copies:

- A loaded mod delivered a fresh updates() sample through shared.json.
- After actual isolated app quit/relaunch, a new nonce received a new reply;
  the persisted old reply was not accepted.
- Switching to a layout without the bridge produced unknown command.
- Switching back restored fresh replies.
- The private core stopped successfully (exit 0, stopped=true).

The screenshot shows the probe label in the isolated window. Its first-start
"Updated to 0.1.16" toast is not evidence of an installed update: networking was
blocked and no update action was dispatched. The sample had checked=null and
checking=true, so it proves transport, not successful network update checking.

## OPEN QUESTIONS

None blocking graduation. Production protocol validation, packaging, concurrency,
installation collision handling and state-machine coverage are explicit PRD work.
Actual version-changing updates remain outside this experiment's proof boundary.

## Disposition

The next experiment is prepared in `native_probe.py`: copied binaries outside
the installed app bundle, a private HC_SESSION and XDG state/config/cache,
a private Herdr home, and a restrictive sandbox that denies IP networking and
writes outside temporary paths. It probes a real window, quits/relaunches that
window, verifies new replies, removes/restores the bridge through test-layout
switches, and cleans up its own app/core in finally blocks.

The host's existing Seatbelt boundary refuses nested sandbox creation with
`sandbox-exec: sandbox_apply: Operation not permitted` (exit 71), including for
`/usr/bin/true`. Tool-level escalation did not remove that outer boundary.
That initial attempt launched no test window. Running without isolation is not a fallback.

The user approved request `6dfead25680c91a6a4405410e7a0a192`. Its app exited
with signal 9 before producing observations. A subsequent isolated --version
probe reproduced that failure; codesign identified missing signed Info.plist
data because the runner had copied bare executables outside their bundles.

The corrected runner preserves complete signed bundles named Probe.app and
Core.app. Both copies pass codesign verification and --version (Herdr 0.1.16,
hc 0.1.21). Probe.app's different name prevents Herdr's hardcoded CLI-link
installer from changing the user's herdr-app link. Short /private/tmp paths
also avoid Darwin Unix-socket path-length limits. The network/write restrictions
and private app/core state remain in place; no signature checks are disabled.

Approved request `c4eb22a215169f9c85428e346437907e` launched the isolated app
and core, then stopped its private core successfully. The mod failed to load:
the prototype treated init's first argument (props) as its context. Herdr calls
init(props, cx). The mocked harness repeated that error, and the check-mode
guard hid it from the initial native check. No fresh response was observed.

The corrected prototype accepts the second argument and uses the spawned
task's context. The harness now supplies the real signature. Both the harness
and a native check with the check-mode guard removed pass; the latter explicitly
exercises initialization. This still does not prove live command delivery.

Request `d28570053c8e9b932b5f92e396967d2b` passed the repeated isolated test.
It wrote `native-result.json` and `native.png` here; both are local experiment
outputs. The runner checks window errors and tolerates a short delay before
the mod accepts commands. The findings above are the durable result record.

Graduate the observed contract into PRD 00157; rebuild production code separately.
No restart of the user's app, app/core update, clone mutation, agent launch, or
change to the user's Herdr configuration was performed. The source can later be replaced
by a supported CLI query if upstream independently adds one, but delivery does
not depend on upstream cooperation.

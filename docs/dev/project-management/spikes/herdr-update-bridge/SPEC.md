# Herdr update bridge spike

## User input

> I have no way of influencing upstream

Context: intake 00157 needs observable update completion. The installed Herdr
API exposes updates() to mods but not to its CLI. Upstream changes cannot be
a delivery dependency. The local bridge is the selected discovery route.

## Smallest demonstrable outcome

A read-only mod returns update state for a unique requested nonce. A client
rejects old replies, including a reply left behind after the mod unloads or
restarts. The mod does nothing during Herdr check mode. This standalone spike
does not execute any app/core update or modify a real Herdr home.

## Observed contract

- Route commands as `<mod>.probe-<32 lowercase hex digits>` through
  Herdr's documented custom-mod command delivery.
- Write a single response to the mod-owned shared-state key
  `sysup.update-probe`, containing schema, nonce and the updates() sample.
- Bound every client probe; accept only its exact fresh nonce. Do not
  use a cached successful probe to authorize an update or restart.
- A small visible layout block keeps the mod loaded; installation alone
  is insufficient. A layout that omits it makes update control unavailable.

## Proof boundaries

The harness supplies the documented Herdr APIs and exercises the exact mod
source. It can establish protocol behavior, check-mode silence, and simulated
instance replacement. It cannot prove real GPUI loading, shared.json flush
timing, app restart recovery, or update completion. Those require an isolated
Herdr runtime. The upstream isolated-display script targets Linux/Weston;
this workspace is macOS. Never use the user's existing window as a substitute.

The isolated native test passed on 2026-11-15: persisted fresh replies, real
quit/relaunch recovery, failure without the layout block and recovery after
restoration. See RESULTS.md for failures corrected and exact proof boundaries.
The production bridge will omit release notes and validate the needed fields.
PRDs 00157–00160 graduate the full intake; this prototype remains disposable.
Delete the spike when its production implementation lands.

# postup F: TUI + text brief (Python derive layer)

<!-- requirements; migrated from PRD 00068 flat file -->

## Overview

### Problem Statement
The brief has no terminal surface: today you open an HTML file or nothing. Discovery (amended by review F4/F6) requires a deterministic CLI text standup as the bare `postup` default and a Textual TUI standup — both driven by one Python derive layer so CLI and TUI render the same view-model (all-interface rule).

### Target Users
Solo developer wanting the standup at a glance in a terminal (incl. over ssh); PRD 00070's cutover, which cannot retire the brief-portfolio skill until this terminal brief exists.

### Success Metrics
- Bare `postup` (and `postup brief`) prints the deterministic text standup from the latest `data.json` on a core-only install — importing no Textual on that path (asserted by test).
- `postup tui` shows attention queue, todos, and repo list; Textual snapshot tests green on the canonical env, auto-skipped elsewhere.
- Both surfaces render identical facts for the same payload (shared derive layer test).
- gems gates green; `postup` extra (textual) wired; CHANGELOG Added entry.

## Functional Decomposition

### Capability: Python derive layer
The deterministic view-model shared by CLI and TUI.

#### Feature: derive module
- **Description**: Compute attention queue, mechanical todos, repo summaries, and since-last diff from the file contracts — the Python counterpart of the frontend's derive (00065).
- **Inputs**: `data.json`, `data-prev.json`, optional `epics.json` under `out_dir`.
- **Outputs**: Typed view-model objects consumed by renderers.
- **Behavior**: Pure functions, no I/O beyond reading the contracts through one loader; missing `epics.json` yields the deterministic subset; missing `data.json` yields a "run postup collect first" state rather than an exception. Parity with the JS derive is enforced through the shared fixture payloads (00065 risk item).

### Capability: Text brief
The default command surface.

#### Feature: brief command (bare default)
- **Description**: `postup` with no subcommand, and `postup brief`, print the text standup.
- **Inputs**: Derive view-model.
- **Outputs**: `CommandResult`; standup text rendered via the console adapter (attention queue, mechanical todos, repo summary, since-last diff).
- **Behavior**: Click group invokes brief when no subcommand is given; the default path imports neither Textual nor any web dependency (lazy imports per AGENTS.md); judgment todos appear only when `epics.json` exists, with a one-line "not enriched" cue otherwise.

### Capability: Textual TUI
The interactive standup.

#### Feature: tui command
- **Description**: `postup tui` opens the Textual standup: attention queue, todos, repo list.
- **Inputs**: Derive view-model; `postup` extra (textual).
- **Outputs**: Interactive TUI; `CommandResult` failure when the extra is missing (`console.require_import()` guidance).
- **Behavior**: Read-only standup view over the same derive output as the text brief; layout changes are gated by snapshot tests (canonical env only, per AGENTS.md); done-state is out of scope here (web owns it until a later decision).

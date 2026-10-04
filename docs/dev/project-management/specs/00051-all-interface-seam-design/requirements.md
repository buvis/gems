# All-interface seam: design doc (decision, no product code)

<!-- requirements; migrated from PRD 00051 flat file -->

## Problem

The stated future goal — every command/action available across CLI, TUI, API, and WebUI — exists as exactly one sentence in `AGENTS.md:67`, with no design doc, no scaffold support, and no parity check. Today's coverage is CLI 16/16, TUI 3/16, API 1/16, WebUI 1/16, and the interfaces that *do* overlap have already drifted (dot TUI reimplements the git layer; the bim PATCH route and TUI create bypass the command classes; the WebUI reports failures as success). Yet the seam that makes the goal reachable **already exists and is proven**: bim's `ACTION_HANDLERS` registry (`serve/_actions.py:175-184`) + command classes + the `bim/dependencies.py` composition root drive CLI, TUI, and API through the same code. What's missing is a written contract that says "this is the seam, every interface consumes it, here is the result-mapping per transport" — so the follow-on refactors (00053–00055, 00057) build to one target instead of re-deciding.

## Solution

Write a design doc, `dev/local/specs/all-interface-architecture.md`, that names the seam concretely, picks the exemplar to standardize on, defines the per-transport result mapping, and gives a parity checklist for "add one new action." No product code changes in this PRD — it is the decision that the refactor PRDs depend on. Pauses for user review (`design_gate: user`).

## Requirements

### Must have
The design doc must specify:
- **The seam**: a per-tool action registry mapping `name → (ParamsType, Command factory that takes injected ports from the composition root and returns `CommandResult`)`, consumed by all four adapters. Reference the working bim exemplar (`_actions.py` handlers + `ACTION_HANDLERS` + generic `POST /actions/{name}` route + YAML `ActionSpec`).
- **Result mapping per transport**: CLI → `console.report_result` (exists); API → `CommandResult.to_dict()` + HTTP status (exists at `result.py:41-50`, currently zero callers); TUI → a `notify_result` helper (to be created); WebUI → typed envelope check in `api.ts` (to be created).
- **The parity checklist**: the exact files that must change to add one new action, per interface, and the rule that the TUI/CLI consume the registry rather than hand-wiring.
- **Migration order**: which existing drifts (00053 dot, 00054 serve/TUI) move onto the seam, and that `dot` is the tool furthest from it.
- **Explicit non-goals**: e.g. tools that stay CLI-only, and that the dual Rust/Python domain stays as-is.

### Nice to have
- A note on extending `dev/bin/scaffold.py` to emit registry stubs for new tools.

## Success Criteria

- `dev/local/specs/all-interface-architecture.md` exists and is specific enough that 00053/00054/00057 need no further architecture decisions.
- User has reviewed the seam choice before the refactors start.

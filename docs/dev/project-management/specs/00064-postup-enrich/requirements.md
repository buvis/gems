# postup B: LLM enrichment via claude CLI

<!-- requirements; migrated from PRD 00064 flat file -->

## Overview

### Problem Statement
The brief's narrative summary, epic grouping, and judgment todos are produced today by Claude hand-writing `epics.json` inside a Claude Code session — welded to one agent and unusable anywhere else. postup must gain the same enrichment as a strictly optional step that shells out to the `claude` CLI, degrades loudly to deterministic mode when it is absent, and owns the prompt so nothing depends on the old skill.

### Target Users
Solo developer running `postup enrich` after `postup collect`; PRDs 00067 (enrich-from-UI trigger) and 00070 (cutover parity) that consume `epics.json`.

### Success Metrics
- With `claude` on PATH: `postup enrich` yields an `epics.json` that passes schema validation; the user is alerted which mode ran.
- Without `claude`: the command warns that quality suffers, continues deterministically, and exits successfully — enrichment never blocks the brief.
- Invalid LLM output triggers exactly one retry, then loud degradation.
- gems gates green (`pytest -m postup`, coverage, mypy strict, ruff, docs, CHANGELOG).

## Functional Decomposition

### Capability: Claude CLI adapter
The only LLM path in postup — no cloud AI SDK.

#### Feature: Availability detection and alerting
- **Description**: Detect whether the `claude` CLI is usable and tell the user what will happen.
- **Inputs**: PATH lookup for `claude`; `PostupSettings.model`.
- **Outputs**: Availability status; console INFO ("enrichment will use claude, model X") or WARN ("claude not found — continuing deterministically; narrative/epics/judgment todos will be missing").
- **Behavior**: Detection is a cheap presence/exec check, run before any prompt is built; absence is a degradation path, never an error.

#### Feature: Headless invocation
- **Description**: Run `claude -p` with the enrichment prompt and capture structured output.
- **Inputs**: Prompt text (see prompt ownership), model from settings (passed only when set — otherwise the CLI's own default is used, see Risks), timeout.
- **Outputs**: Raw model response text.
- **Behavior**: Subprocess shell-out mirroring the gh-CLI delegation pattern; non-zero exit, timeout, or empty output degrade loudly per the retry rule below.

### Capability: Enrichment pipeline
From collected data to a validated `epics.json`.

#### Feature: enrich command
- **Description**: `postup enrich` turns `data.json` + `commits-digest.md` into a schema-valid `epics.json`.
- **Inputs**: The 00063 file contracts under `out_dir`.
- **Outputs**: `CommandResult`; `epics.json` written via `atomic_write`.
- **Behavior**: Build prompt → invoke → parse JSON → validate against the epics schema. On parse/validation failure: one retry (with the validation errors appended to the prompt), then WARN and continue deterministically without writing a partial file. Stale-input guard: if `data.json` is missing, return a failure `CommandResult` telling the user to run `postup collect` first.

#### Feature: Epics schema
- **Description**: Pydantic schema that `epics.json` must satisfy.
- **Inputs**: Parsed LLM JSON.
- **Outputs**: Validated model: portfolio `summary`, per-repo epics referencing exact commit SHAs, judgment todos with stable ids, urgency, and importance/effort fields.
- **Behavior**: SHAs are cross-checked to exist in `data.json`'s commit set (guards hallucinated references); todo ids must be stable across runs so done-state tracking survives re-enrichment.

#### Feature: Prompt ownership
- **Description**: The enrichment prompt and epic/todo rules move from the skill into the gem.
- **Inputs**: Current prompt logic in `~/.claude/skills/brief-portfolio/` (narrative, epic grouping, judgment-todo rules).
- **Outputs**: Versioned prompt module inside postup; no runtime or content dependency on the skill remains.
- **Behavior**: Prompt is assembled from the digest with a size guard for large portfolios (see Risks — strategy is an open decision for design).

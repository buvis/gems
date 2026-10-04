# bim: route every interface through the command classes

<!-- requirements; migrated from PRD 00054 flat file -->

## Overview

### Problem Statement
bim's interfaces have drifted off the shared seam in four concrete places, so the same action behaves differently depending on where you invoke it:
- **PATCH route writes inline**, bypassing `UpdateZettelUseCase`: it mutates the data dict, formats, and `fp.write_text` directly (`src/tools/bim/commands/serve/_routes.py:136-157`), while the same server's `handle_patch` correctly uses the use case (`_actions.py:36-44`). Section-replace logic exists twice.
- **WebUI shows failures as success**: action handlers return HTTP 200 with `{"status":"error"}` (`_actions.py:62-64,87-89,…`); `api.ts` only throws on `!res.ok`; `ActionBar` reports "done" regardless.
- **TUI create bypasses `CommandCreateNote`**: `tui/create_note.py:163-181` calls `CreateZettelUseCase` directly, so required-answer validation and default-fill (`commands/create_note/create_note.py:43-49`) never run — the TUI can create notes with empty required answers.
- **Screens discard `CommandResult`**: `EditScreen._save` (`tui/edit_note.py:190-198`) drops the result, so TUI edit failures vanish silently. `CommandResult.to_dict()` ("for API responses", `result.py:41-50`) has zero callers.

### Target Users
Bob across bim CLI/TUI/WebUI; anyone relying on the interfaces agreeing.

### Success Metrics
- Every serve route and TUI action goes through a command class / use case (no inline writes).
- A failed action is reported as a failure in the WebUI and the TUI.
- One result envelope: handlers return `CommandResult.to_dict()` + a mapped HTTP status.

## Functional Decomposition

### Capability: Single write path
All note mutations flow through the command classes / use cases; no interface writes inline.

#### Feature: PATCH via UpdateZettelUseCase
- **Description**: delete the inline write in the PATCH route; delegate to the use case (as `handle_patch` already does).
- **Inputs/Outputs/Behavior**: same request; one code path; consistency/downcast rules apply everywhere.

### Capability: Uniform result reporting
Every transport maps `CommandResult` the same way.

#### Feature: Envelope + HTTP status
- **Description**: handlers return `result.to_dict()`; the route maps `success=False` to 4xx/5xx; WebUI checks the envelope; TUI screens notify on failure.
- **Inputs/Outputs/Behavior**: per the result-mapping contract in `dev/local/specs/all-interface-architecture.md`.

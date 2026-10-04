# postup C: web frontend core (SvelteKit skeleton + derive port + core views)

<!-- requirements; migrated from PRD 00065 flat file -->

## Overview

### Problem Statement
The brief's web UI is a Svelte 5 + Vite SPA (2,551 lines, 12 components) baked into a single HTML file inside the skill — outside the repo's frontend convention and untested except for `lib/derive.js`. The discovery decision (Q5) is a SvelteKit rebuild mirroring bim's frontend subtree, keeping one frontend convention in the repo. This PRD lands the app skeleton, the ported derive logic (tests first), and the first three views; 00066 adds the rest; 00067 serves it.

### Target Users
Solo developer viewing the portfolio brief in a browser (via 00067 serve); PRD 00066 building on the skeleton.

### Success Metrics
- Ported `derive` test suite green against fixture `data.json`/`epics.json` payloads before any view work starts.
- Brief, Todos, and Repos views render the full deterministic content from a fixture payload (no LLM, no server).
- Done-state (checked-off todos) persists across reloads and is pruned against payload ids.
- Committed production build exists (bim pattern); ruff/mypy untouched surfaces stay green; CHANGELOG Added entry.

## Functional Decomposition

### Capability: Frontend foundation
The SvelteKit app skeleton and its data feed.

#### Feature: SvelteKit subtree
- **Description**: SvelteKit app mirroring bim's frontend layout (committed build, single frontend convention).
- **Inputs**: bim exemplar `src/tools/bim/commands/serve/frontend/`; SPA source as reference.
- **Outputs**: `frontend/` subtree under postup with dev tooling, plus a committed production build consumed by 00067.
- **Behavior**: Static-adapter build; no server-side rendering requirement; build artifacts committed per bim precedent.

#### Feature: Payload plumbing
- **Description**: One data path feeding views in dev and in prod.
- **Inputs**: `data.json` + optional `epics.json` (+ `data-prev.json`, `history.jsonl` for 00066 features).
- **Outputs**: A typed store/loader the views consume.
- **Behavior**: In dev, fixture payloads load directly; in prod the loader fetches from the 00067 endpoints. Loader is the single seam — views never read files or URLs themselves. Absent `epics.json` renders the deterministic subset (mechanical todos only), mirroring the CLI degradation story.

### Capability: Derived view-model
The pure logic layer — ported first, tests first.

#### Feature: derive port
- **Description**: Port `lib/derive.js` (345 lines, the SPA's only tested module) and its test suite to the new app.
- **Inputs**: Fixture payloads generated from the 00063 contract.
- **Outputs**: Derive module producing attention queue, mechanical todos, repo summaries, and the inputs the views bind to.
- **Behavior**: Tests are ported/translated before the implementation is wired to views; behavior parity with the SPA is the acceptance bar (same fixtures → same derived values).

### Capability: Core views
The first three tabs.

#### Feature: Brief, Todos, Repos views
- **Description**: The narrative brief, the todo list, and the repo list — the SPA's core tabs rebuilt.
- **Inputs**: Derived view-model.
- **Outputs**: Three routed views with the SPA's information content (visual parity informal per discovery Q9).
- **Behavior**: Brief shows summary + epics when enriched data exists, deterministic content otherwise; Todos merges mechanical + judgment todos with done-state checkboxes; Repos lists per-repo status including `errors[]` badges.

#### Feature: Done-state
- **Description**: Persist which todos the user marked done.
- **Inputs**: Todo ids (stable ids from 00064 for judgment todos, deterministic ids for mechanical todos).
- **Outputs**: Persisted done set, pruned to ids present in the current payload.
- **Behavior**: localStorage port of the skill's `brief-portfolio-done` key under a postup key — parity baseline. Server-side persistence is a nice-to-have owned by 00067 (open decision there); the storage access sits behind one small store so the swap is local.

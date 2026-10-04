# klyreon B: ingest, agent backend, contradiction detection

<!-- requirements; migrated from PRD 00075 flat file -->

## Overview

### Problem Statement
A source file dropped into the vault is inert until something reads it, interrogates it, and turns it into claim-bearing zettels. That is the whole product: without ingest there is no compounding, no contradiction detection, and nothing for maintenance to maintain. PRD A made the vault readable, writable, and commitable; this PRD makes it grow on its own, bounded so a hung operator CLI can never wedge a cron schedule, and staged so a failed source leaves no trace.

### Target Users
The vault owner, running `klyreon ingest` by hand today and from cron after PRD D. Also PRD D's maintenance sweep, which counts the corroboration and conflict structures this PRD writes.

### Success Metrics
- Discovery criterion 1: one fixture source per spec source type (article, book, quote, transcript) ingests with zero human interaction and produces zettels that `klyreon validate` reports clean.
- Discovery criterion 2: five crafted fixture sources conflicting with an existing accepted claim each resolve into exactly one of aporia, refine, supersede, on three consecutive runs of the whole fixture set. No conflict is left as silent coexistence.
- Discovery criterion 5: a source whose backend call is killed leaves no zettel, no trail entry claiming success, no archive move, and no resume state; the next run re-processes it.
- Discovery criterion 6: fixture output passes the eight-rule quality rubric below, run as a test.
- With a stub backend, the whole pipeline runs offline in CI: no network, no operator CLI installed.
- gems gates green: `pytest -m klyreon`, ≥50% tool coverage, mypy strict, ruff, docs, CHANGELOG.

## Functional Decomposition

### Capability: Agent backend abstraction
The seam between klyreon's deterministic loop and the operator CLI that does the semantic work.

#### Feature: Backend contract
- **Description**: One narrow interface every operator adapter implements.
- **Inputs**: A prompt string and a timeout in seconds.
- **Outputs**: A parsed, schema-validated JSON payload, or a `BackendError` carrying the reason (`timeout`, `exit`, `parse`, `schema`).
- **Behavior**: The backend is a pure text-in, JSON-out function. It gets no filesystem access to the vault and writes nothing. Three reasons: deterministic work belongs in code (AGENTS.md `ai-app-design`); output must be mechanically validated before it becomes a file (the 35%-no-frontmatter finding in `anti-example-prior-build-output.md`); and atomic staging only works if klyreon owns the entire write set. A `StubBackend` returning canned payloads is part of the shipped code, so every pipeline test runs offline.

#### Feature: Claude adapter
- **Description**: Drive Claude Code headless.
- **Inputs**: The prompt on stdin, `KlyreonSettings.model` when set, the per-source timeout.
- **Outputs**: The payload extracted from the CLI's response.
- **Behavior**: Runs `claude -p --output-format json --json-schema <IngestPayload schema> --tools ""` (plus `--model` when configured) with the prompt on stdin, `cwd` set to a temporary directory, and a hard `subprocess` timeout. `--tools ""` is what actually enforces the no-filesystem-access half of the backend contract; the temp `cwd` alone only makes vault access inconvenient. `--json-schema` is fed the `IngestPayload` schema, so shape validation happens in the CLI rather than in hand-rolled parsing: klyreon parses the JSON envelope, takes its result field, and validates against the pydantic model — a response that still does not match is a `BackendError(reason="schema")`, never a salvage attempt. A missing `claude` binary is a clear failure naming the tool, not a traceback. Flags verified against `claude --help` on 2026-08-07 (backlog review); the docs page records this invocation and pins the known-good CLI version, and the adapter is the one place to re-verify when the operator CLI updates.

#### Feature: Prompt library
- **Description**: The ingest prompt ships inside the package.
- **Inputs**: Source frontmatter and body, `<root>/voice.md`, the split rule, the claim set from `klyreon export-claims`, the response schema.
- **Outputs**: One assembled prompt string.
- **Behavior**: Templates live at `src/tools/klyreon/prompts/*.md` and load through `importlib.resources`. The loop never depends on files installed into an operator's home directory (PRD C installs those for the human's interactive use, not for this pipeline). When `<root>/voice.md` is missing, a built-in default voice is used and the run warns.

### Capability: Ingest pipeline
Source document to committed zettels, one source at a time.

#### Feature: Inbox sweep and run bounds
- **Description**: `klyreon ingest [PATH]` picks the work and bounds it.
- **Inputs**: No argument sweeps `sources/*/` excluding `sources/archive/`; a file path ingests that one file, copying it into `sources/YYYY-MM/` first when it lies outside the vault. Flags: `--max-sources`, `--timeout`, `--dry-run`.
- **Outputs**: `CommandResult` summarising per-source outcomes; exit 1 when any source failed.
- **Behavior**: Refuses in a non-git vault through PRD A's autonomy gate. Processes at most `max_sources_per_run` (default 5) sources in filename order; the remainder waits for the next run and is named in the trail. Each source gets `source_timeout_seconds` (default 900) of wall clock; on expiry the backend process is killed, the source's staged work is discarded, and the run continues with the next source. `--dry-run` runs the backend and reports what would land without applying anything. Ingesting a directory of external files is out of scope for v1; the inbox sweep is the batch path.

#### Feature: Single-instance guard
- **Description**: Two klyreon runs never touch one vault at once.
- **Inputs**: The resolved root.
- **Outputs**: Either the held lock or a clean exit.
- **Behavior**: A non-blocking `fcntl.flock` on `$XDG_STATE_HOME/klyreon/<sha256(root)[:12]>.lock`, held for the run and released in `finally`, so `KeyboardInterrupt` and every other `BaseException` release it and process death releases it at the kernel level (the claim-release invariant). An invocation that cannot take the lock prints an info line and exits 0: overlapping cron ticks are expected, not an error. PRD D reuses this module.

#### Feature: Per-source pipeline
- **Description**: The one-call loop that turns a source into zettels.
- **Inputs**: One source document, the claim set, the voice, the split rule.
- **Outputs**: A staged set of new zettels, edits to existing zettels, MOC updates, and the archive move.
- **Behavior**: Archive-first (discovery Q15): the archive path `sources/archive/YYYY-MM/<name>.md` is resolved before the backend call, and every derived zettel cites it from birth, so no path is ever rewritten. One backend call per source carries the source body, the voice, the split rule, and the full claim set, and returns new zettels plus conflicts plus corroborations in one payload; extraction and cross-comparison in one pass is what the claim set exists for (spec 7.5). Rendering is code: klyreon allocates each ID with PRD A's collision rule, sets `sources`, `assent: tentative`, `lifecycle: fleeting`, `processed: false`, writes the H1 from the title, and materialises links. Every rendered file must pass `validate_file` plus the split rule before it is staged; a violation fails the source with the rule named in the trail.

#### Feature: Split rule
- **Description**: The concrete ceiling that "one zettel, one idea" needs to be enforceable.
- **Inputs**: A rendered zettel.
- **Outputs**: Pass, or a named violation.
- **Behavior**: A zettel carries one to three claims (spec 7.5) and a body no longer than `max_zettel_body_lines` (default 60). The prompt states the rule; the code enforces it. This is the answer to the 411-line, 11-section specimen in the anti-example. A source that keeps violating it keeps failing and keeps returning on the next run, consuming one slot: the fix is to split or drop the source, and the trail names it every time.

#### Feature: Atomic staging and apply
- **Description**: A source lands entirely or not at all.
- **Inputs**: The staged set for one source.
- **Outputs**: One git commit per source, or an untouched vault.
- **Behavior**: Staging lives under `$XDG_STATE_HOME/klyreon/staging/<run-id>/<source>/`, mirroring vault-relative paths, and is deleted at the end of the source either way; it is scratch, never resume state (discovery Q16). Apply order: write new and edited zettels, write MOC updates, move the source into the archive, then commit exactly those paths with PRD A's scoped commit. Any exception during apply rolls back: written files are removed and the archive move is reversed. A hard kill during apply can still leave uncommitted files in the working tree; that window is milliseconds of file writes, `klyreon validate` reports it, and `git checkout`/`git clean` fixes it. Marked with a `ponytail:` comment naming a two-phase-commit upgrade path if it ever bites.

### Capability: Contradiction and corroboration
The single-pass comparison that makes the vault compound instead of accumulate.

#### Feature: Conflict resolution into three shapes
- **Description**: Every detected conflict becomes exactly one structure. None coexists silently.
- **Inputs**: Conflict entries from the payload: the new claim, the target zettel and claim, the shape, a rationale.
- **Outputs**: Links and doubts on the new zettel, and the minimum edit on the existing one.
- **Behavior**: **aporia**: `contradicts` on both sides (a symmetric relation is materialised both ways) plus a `disagreement` doubt with a `target` on both sides, so the reciprocity that spec 7.6 derives aporia from actually exists; the backend may also return a claim-less `concept-type: aporia` zettel, and klyreon writes it when it does. **refine**: `narrower-than` from the new zettel to the target only; the `broader-than` inverse is derived at query time, never stored (spec 8). **supersede**: `supersedes` from the new zettel to the target, and the target moves to `assent: rejected`. Editing an existing zettel's doubts is a content change, so it resets `processed: false` and bumps `updated`; the supersede loser's assent-only change does neither (spec 7.7). A conflict whose target zettel already carries `assent: rejected` is dropped by code before any edit and logged in the trail as corroborating the existing rejection (discovery Q13), whatever the backend proposed.

#### Feature: Corroboration recording
- **Description**: Agreement from a different source is recorded so promotion can count it.
- **Inputs**: Corroboration entries from the payload.
- **Outputs**: A `supports` link from the new zettel to the corroborated one.
- **Behavior**: `supports` ("A provides evidence for B") is the existing relation for this, so no vocabulary change is needed and the cap of ten holds. The corroborating zettel's own `sources` entry is what makes the source distinct, which is exactly what PRD D's "two corroborations from different sources" rule counts. The corroborated zettel is not edited.

#### Feature: MOC authoring
- **Description**: A zettel that anchors to a MOC finds one there.
- **Inputs**: `mocs` paths on the rendered zettels.
- **Outputs**: Created or updated MOC files.
- **Behavior**: A missing MOC is created with `id` (the kebab filename stem), `title`, `created`, `kind: moc`, an H1, and an empty member block delimited by `<!-- klyreon:members -->` and `<!-- /klyreon:members -->`. New members are appended inside that block as Markdown links; klyreon rewrites only the block, so anything the human wrote around it survives (the human-edits-win rule). PRD D (00077) reconciles membership on every maintain sweep.

### Capability: Run journal
What the machine did, readable without git log.

#### Feature: Trail file per run
- **Description**: Every ingest run writes one trail.
- **Inputs**: The per-source outcomes of the run.
- **Outputs**: `wiki/trails/YYYYMMDDHHmmSS.md` with `kind: trail`, `run: ingest`.
- **Behavior**: One file per run (discovery Q14), written and committed at the end of the run as its own commit; per-source atomicity covers each source's own writes, so the two rules do not collide. Sections: sources committed, sources failed with the reason, sources deferred by the cap, zettels created, each conflict and the shape it resolved into, corroborations, MOCs touched. A run that dies before writing the trail leaves the per-source commits as the record. No retention rule in v1: the files are small, git-tracked, and deleting them is a decision the owner has not asked for.

# klyreon A: gem scaffold, spec engine, vault contract, git layer

<!-- requirements; migrated from PRD 00074 flat file -->

## Overview

### Problem Statement
Klyreon is a personal Memex-Zettelkasten that an LLM maintains mostly on its own: sources become interrogated, claim-bearing zettels, and every new claim is checked against existing knowledge at ingest. The format spec is written and validated, but nothing reads or writes it. Without a spec engine, a vault contract, and a git layer that separates machine writes from human ones, the two autonomous PRDs that follow (ingest, maintain) have no substrate: they cannot validate what they produce, cannot resolve a root-relative path, and cannot commit under an identity that makes authorship detectable.

### Target Users
The vault owner (Bob), running klyreon by hand today and from cron after PRD D. Also the three follow-on PRDs (00075 ingest, 00076 operator assets, 00077 maintain + schedule), which consume the document model, the claim-set export, and the git layer built here.

### Success Metrics
- `klyreon init` on an empty directory produces a layout that `klyreon validate` reports clean, and a second `init` changes nothing.
- `klyreon validate` fails with a located, human-readable error on every fixture in a crafted invalid-vault corpus (one fixture per spec rule below), and exits 0 on the valid corpus.
- Round-trip: parse then serialize every fixture file byte-for-byte except for fields the writer deliberately normalizes; unknown frontmatter keys survive.
- `klyreon export-claims` on a 200-zettel fixture vault emits valid JSON carrying every claim with its parent's `assent`, `lifecycle`, and root-relative path.
- In a non-git vault, `init`, `validate`, `new`, `export-claims`, `status` succeed and warn; the autonomy gate reports "refused" for the mutating commands reserved by later PRDs.
- gems gates green: `pytest -m klyreon`, ≥50% tool coverage, mypy strict, ruff, docs page, CHANGELOG entry. Core-only install (`uv tool install buvis-gems`) runs every command: no new dependency.

## Functional Decomposition

### Capability: Gem scaffold and wiring
Everything that makes `klyreon` tool 17 in the monorepo.

#### Feature: Tool scaffold
- **Description**: Generate the gem with `dev/bin/scaffold.py` and wire it into the repo.
- **Inputs**: Tool name `klyreon`, description "Autonomous Memex-Zettelkasten". Premise: `src/tools/klyreon/` does not exist. Re-check at execution time; if it exists, stop and report rather than overwrite.
- **Outputs**: `src/tools/klyreon/` with `manifest.toml` (interfaces: cli only), `cli.py`, `settings.py`, `commands/`; console script `klyreon = klyreon.cli:cli`; wheel package and `klyreon` pytest marker registered; `tests/tools/klyreon/`; `docs/source/tools/klyreon.rst`; CHANGELOG Added entry.
- **Behavior**: No `[project.optional-dependencies]` entry: klyreon runs on the core install. `buvis_options` on the CLI group. Command classes imported lazily inside handlers. `dev/bin/check_tool_wiring.py` passes.

#### Feature: Klyreon settings
- **Description**: `KlyreonSettings(GlobalSettings)` for everything that is not the vault root.
- **Inputs**: gems config resolver, env `BUVIS_KLYREON_*`, `--config`.
- **Outputs**: `backend` (default `claude`), `model` (optional), `max_sources_per_run` (5), `source_timeout_seconds` (900), `max_zettel_body_lines` (60), `maintenance_window_days` (7), `pruning_enabled` (false), `prune_window_days` (365), `git_identity_name` (`klyreon`), `git_identity_email` (`klyreon@localhost`).
- **Behavior**: Vault-scoped keys never live here. The root comes from klyreon's own config file (below), per spec 10, because any tool reading the vault must find the root the same way.

### Capability: Vault contract
How klyreon finds the vault and creates it.

#### Feature: Root discovery
- **Description**: Resolve the vault root and every root-relative path in a file.
- **Inputs**: `$KLYREON_ROOT`, else `$XDG_CONFIG_HOME/klyreon/config.yaml` (falling back to `~/.config/klyreon/config.yaml`), key `root`.
- **Outputs**: An absolute, existing `Path`, or a loud failure naming which rule broke.
- **Behavior**: `$KLYREON_ROOT` wins (spec 10.1 reason 2: test isolation). `~` expands. A relative root, a missing root directory, or a missing config file fails loudly and never creates directories. `resolve_path(rel)` rejects any path containing `..` and any path that resolves outside the root (spec 10.4).

#### Feature: init command
- **Description**: `klyreon init [PATH]` creates the vault skeleton and the config that points at it.
- **Inputs**: Target directory (default: cwd), `--force` to overwrite an existing config.
- **Outputs**: `<root>/sources/`, `<root>/wiki/notes/`, `<root>/wiki/mocs/`, `<root>/wiki/trails/`, `<root>/voice.md` starter, `~/.config/klyreon/config.yaml` with `root:`; `CommandResult` listing what it created and what it left alone.
- **Behavior**: Idempotent: existing directories and files are left untouched and reported as existing. Rewriting a config that points elsewhere needs `--force`. Warns when `<root>` is not inside a git work tree, naming `git init` as the user's job (discovery Q12: klyreon never creates the repo). It never runs `git init`. PRD C adds the operator-asset offer, PRD D the schedule offer.

### Capability: Spec engine
Parse, validate, and write both file species plus the auxiliary files.

#### Feature: Document model and round-trip
- **Description**: One model per file kind, with lossless read and write.
- **Inputs**: A Markdown file with YAML frontmatter.
- **Outputs**: A typed document (frontmatter fields, unknown fields, body) and a serializer that writes it back.
- **Behavior**: Kind is decided by directory: `sources/**` is a source document, `wiki/notes/*` is a zettel, `wiki/mocs/*` and `wiki/trails/*` are auxiliary files. YAML loads with the sexagesimal int resolver stripped and `id` kept as a string, so `id: 20260411145300` never becomes an integer (the trap `pybase.zettel._ZettelSafeLoader` already solved). Unknown frontmatter keys are preserved and written back after the known keys, in their original order (spec 14). Known keys are written in spec order. Every write goes through `pybase.filesystem.atomic_write`; no bare `Path.write_text` anywhere in the tool.

#### Feature: File-level validation
- **Description**: Check one file against the spec rules that need only that file.
- **Inputs**: A parsed document plus its path.
- **Outputs**: A list of errors, each carrying path, line where derivable, rule id, and message.
- **Behavior**: Rules: required fields `id`/`title`/`created`/`type` (auxiliary files use `kind` in place of `type`); `id` equals the filename stem; zettel filename is exactly 14 digits and `created` agrees with it to the second; exactly one H1 and its text equals `title`; `type` in the closed enum for the file's species; source-document types never appear in `wiki/notes/` and zettel types never in `sources/`; `concept-type`, `assent`, `lifecycle`, `claims`, `doubts` absent on source documents; `concept-type`/`assent`/`lifecycle`/doubt `mode`/link `rel` in their closed enums; `claims` non-empty on `concept-type` in {`thesis`, `argument`, `observation`} and absent on `aporia`; each claim has `id` and `statement`; each doubt has `mode`, `claim`, `rationale`, and `target` (with `to` and `claim`) when `mode: disagreement` names foreign material; each `links` entry has `rel` and `to`; `publish` never `true` when written by a tool.

#### Feature: Vault-level validation and the validate command
- **Description**: `klyreon validate` runs every mechanical check over the whole vault.
- **Inputs**: The resolved root; `--json` for machine output.
- **Outputs**: `CommandResult`; exit 1 when any error exists, 0 when clean.
- **Behavior**: Adds the checks that need the graph: every `sources`, `links.to`, `mocs`, and `doubts[].target.to` path resolves under the root and exists; `links.to` targets a zettel, never a source document; no cycle in the transitive relations `requires`, `broader-than`, `narrower-than` (spec 8); colon-prefixed legacy tags flagged; concept zettel with no `mocs` flagged as an orphan; body longer than `max_zettel_body_lines` flagged as oversized; `reviewed` older than `updated` flagged as a stale review. PRD D's `maintain` reuses this same engine rather than reimplementing lint.

### Capability: Authoring and export
Creating zettels, and handing the claim set to a caller.

#### Feature: new command with the collision rule
- **Description**: `klyreon new` writes one spec-valid zettel with a unique ID.
- **Inputs**: `--type` (zettel type, default `note`), `--title`, `--concept-type` (optional; makes it a concept zettel).
- **Outputs**: The created file path on stdout; `CommandResult`.
- **Behavior**: ID is the local-time creation timestamp as 14 digits. If `wiki/notes/<id>.md` exists, bump by one second and retry until free; filename and `created` always agree (spec 3.1). Concept zettels get `assent: tentative`, `lifecycle: fleeting`, `processed: false`. Utility zettels get none of the concept fields. H1 equals `title`. The result validates.

#### Feature: export-claims command
- **Description**: `klyreon export-claims` emits the claim index that the ingest contradiction pass reads.
- **Inputs**: The vault; `--out PATH` (default stdout).
- **Outputs**: JSON: `{"schema_version": 1, "generated": "<iso>", "claims": [{"zettel": "wiki/notes/....md", "assent": "...", "lifecycle": "...", "claim_id": "c1", "statement": "..."}]}`.
- **Behavior**: Every claim in the vault, including claims on `assent: rejected` zettels, which arrive labelled so a caller can tell a conflict with endorsed material from a conflict with material the vault already refused (discovery Q13). JSON, not Markdown, because the consumers are prompt assembly and `jq`. `--out` refuses any path that resolves under the vault root: the claim set is derived state, and the vault holds only knowledge (discovery constraint). Whole vault today; the command takes an optional scope argument later without changing callers.

### Capability: Git layer and autonomy gate
The seam that separates machine writes from human ones, and the precondition for autonomy.

#### Feature: Scoped klyreon commit
- **Description**: Commit exactly the paths klyreon wrote, under the klyreon identity.
- **Inputs**: A list of vault-relative paths, a commit subject.
- **Outputs**: The commit SHA, or a failure.
- **Behavior**: `git -C <root> add -- <paths>` then `git -C <root> commit -- <paths>` with `-c user.name=` / `-c user.email=` from settings, so the identity is set per invocation and the user's global git config is never touched. Pathspec scoping is what makes an uncommitted human edit elsewhere in the tree survive untouched: it stays modified and unstaged. Nothing ever calls `git add -A`.

#### Feature: Autonomy gate and authorship
- **Description**: One check that mutating commands consult, plus the query that tells machine commits from human ones.
- **Inputs**: The resolved root.
- **Outputs**: `is_git_vault() -> bool`; `require_git_for_autonomy()` returning a `CommandResult(success=False)` with the warning text; `is_human_authored(path) -> bool`.
- **Behavior**: In a non-git vault, `ingest` and `maintain` (PRDs B and D) refuse and exit 1: neither the git archive that pruning relies on nor authorship detection exists there. `init`, `validate`, `new`, `export-claims`, and `status` still run and warn. Authorship reads `git log --format=%an -- <path>`: any commit whose author name is not the configured klyreon identity means a human touched the file. This PRD ships the gate and its tests; PRDs B and D call it.

### Capability: Vault status
The health surface, and the reminder that maintenance has not run.

#### Feature: status command and staleness warning
- **Description**: `klyreon status` prints the vault dashboard; every invocation of every command warns when maintenance is stale.
- **Inputs**: The vault; `$XDG_STATE_HOME/klyreon/state.json` (`last_maintain`).
- **Outputs**: Counts by `lifecycle` and `assent`, total zettels and sources, mean links per zettel, count of `concept-type: aporia` zettels and of open `disagreement` doubts, pending sources in the inbox, git status of the vault, staleness line.
- **Behavior**: Everything is computed from the vault on demand; no index file, no wiki-level `index.md`/`log.md`/`lint-report.md` (discovery Q14). `evergreen` plus `literature` counts are the promotion proxy that success criterion 4 watches, so no per-run counter is needed. The staleness check runs from the CLI group callback: absent or older than `maintenance_window_days` warns through the console. PRD D writes `last_maintain` and adds the prune-candidate count.

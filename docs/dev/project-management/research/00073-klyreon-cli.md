# Discovery: Klyreon CLI

## Classification
Depth: comprehensive | Date: 2026-08-05, extended 2026-08-06 (Q12-Q20)

## Problem
Knowledge accumulated from articles, transcripts, and reading is either lost or re-derived on every question; RAG-style retrieval does not compound. Klyreon is a personal Memex-Zettelkasten maintained mostly autonomously by an LLM: sources are ingested into interrogated, claim-bearing zettels, every new claim is checked for contradictions against existing knowledge at ingest, and noise is surfaced for pruning before it becomes overload (deletion stays opt-in, Q19). It stays fully separate from the manual ~/bim vault; the human is the only bridge. The product is the CLI that controls this system. Without it, the validated format spec stays theory and the compounding loop never runs.

## Requirements

### Must have
- CLI command surface (v1): `klyreon init`, `klyreon validate`, `klyreon new`, `klyreon ingest`, `klyreon maintain`, `klyreon status`, `klyreon schedule` (install/status/uninstall), plus a claim-set export command (exact name in design) - agents, tests, and debugging invoke it directly. Every capability below is reachable from one of these.
- Spec engine: parse and validate both file species against `docs/reference/klyreon/zettel-format-specification.md` (required fields, closed enums, ID/filename/`created` agreement, root-relative path resolution, H1/title match, claims MUST on assertion-bearing shapes, unknown-field preservation on rewrite).
- `klyreon init`: create vault skeleton (`sources/`, `wiki/notes|mocs|trails`), write XDG config, offer operator-asset installation and `klyreon schedule install`. It never runs `git init` (Q12).
- Git integration: klyreon commits its own writes under a klyreon identity so authorship separates machine from human, and warns when the vault is not a git repo. The repository is the user's to create. Git is the precondition for autonomy: in a non-git vault, autonomous mutation is disabled entirely - ingest and maintain refuse with a warning (init, validate, status, new still work), since neither the git archive nor authorship detection exists there.
- Collision-safe zettel creation (`klyreon new`) implementing the ID bump rule.
- Claim-set export: the claim index used for single-pass cross-comparison, emitted for a requested scope (whole wiki by default, narrowable later without changing callers). Each entry carries the claim id and statement plus its parent zettel's `assent`, `lifecycle`, and root-relative path, so the detector can separate a conflict with an endorsed claim from a conflict with one the vault already rejected (Q13).
- Agent backend abstraction with pluggable operator CLIs - claude (Claude Code) first; kiro and copilot follow-up. Operator-specific assets (skills, rules, agents) ship with the product.
- Operator asset installation: `klyreon init` asks which operators the user runs (claude, kiro, copilot, ...) and installs the matching asset files (skills, rules, steering, agent definitions) into each operator's expected location. Installation is re-runnable later to add or refresh an operator without re-initializing the vault.
- Operator asset refresh: klyreon tracks what it installed where in a manifest that records a content hash per file, and refreshes those files on demand, warning when installed assets are older than the CLI. A file the user has edited is backed up beside itself before being overwritten, and every displaced file is reported (Q18). Binary upgrade is the buvis-gems updater's job, not klyreon's.
- `klyreon schedule install|status|uninstall`: writes a launchd plist on macOS or a crontab line on Linux driving the unattended run (bounded ingest, then maintain), records it in the same manifest as operator assets, and is re-runnable after a machine change without touching the vault (Q17).
- Ingest is atomic per source: new zettels, conflict edits to existing zettels, the source archive move, and the trail entry are staged and applied together. A failed or timed-out source leaves the vault untouched and the source in `sources/YYYY-MM/`; re-running is a clean retry, with no resume state on disk (Q16).
- Run bounds for unattended operation: a max-sources-per-run cap (small default, remainder waits for the next run) and a per-source wall-clock timeout, so a hung operator CLI can never wedge the schedule (Q20). Plus a vault-level single-instance guard: an invocation that finds another klyreon run live against the same vault exits cleanly without touching it.
- Run journal: every ingest and maintain run writes one trail file under `wiki/trails/` (`YYYYMMDDHHmmSS.md`) recording sources ingested, zettels created, each conflict and the shape it resolved into, promotions, and prune candidates or prunes (Q14).
- `klyreon ingest`: source document -> interrogated concept zettels in the vault voice (claims mandatory on assertion-bearing shapes, doubts where noticed, relations and MOC anchors actively sought, one idea per zettel enforced by a concrete split rule with the size ceiling in config), cross-comparison of every new claim against the full claim set (contradiction check plus corroboration detection: agreement from a different source is recorded, shape per design, so maintain's deterministic promotion rule can count it), `processed: false`, `updated` bump, source archive move with every derived zettel citing `sources/archive/YYYY-MM/...` from birth so no path is ever rewritten (Q15). Every detected conflict resolves into exactly one of three shapes (spec 8): **aporia** (`disagreement` doubts with `target` on both sides, optional claim-less aporia zettel), **refine** (`narrower-than`), or **supersede** (`supersedes` link, loser to `assent: rejected`).
- MOC authoring: ingest creates a missing MOC file when it anchors to one, and maintain keeps MOC membership in sync (format resolved in design; minimum: an H1 title plus a list of member zettel paths).
- `klyreon maintain`: idempotent, cron-safe sweep - lint (orphans, dangling paths incl. `doubts[].target`, legacy colon-tags, enum violations, stale reviews, transitive-relation cycles, oversized zettels), rule-driven lifecycle promotion, rule-driven assent transitions (2 corroborations from different sources -> accepted; open disagreement holds), and prune-candidate detection for orphaned uncorroborated fleeting zettels past the window (`rejected` and non-empty `delivered-as` exempt). Rule-driven assent/lifecycle transitions MUST NOT reset `processed` (spec 7.7). Each transition is atomic per zettel (a prune's delete and its inbound-link cleanup land together); an interrupted sweep leaves a validate-clean vault and the idempotent re-run completes the remainder.
- Pruning is report-only by default (Q19): maintain lists candidates in the trail entry and in `status` but deletes nothing until the owner enables pruning in config, at which point the window defaults to 365 days and deletion cleans inbound links, with git history as the archive.
- Dry-run mode for maintain: report what would be pruned/promoted without touching files.
- `klyreon status`: vault health dashboard (counts by lifecycle/assent, links per zettel, promotion count, unresolved aporias, prune candidates).
- Staleness warning on every invocation when maintenance has not run within its window.
- No autonomous operation (any scheduled or unattended run) may require human input; interactive setup (init, schedule install) may prompt. Human edits/overrides always win and are never reverted by automation. Authorship is determined from git history: commits not made by klyreon are human.

### Nice to have
- Ingest batch mode over an arbitrary external directory (the unattended run already sweeps the `sources/` inbox).

### Out of scope (v1)
- Creating the vault's git repository: klyreon commits and warns, the user runs `git init` (Q12).
- Wiki-level files beyond trails - `index.md`, `log.md`, `lint-report.md`, `arrangements/`: `status` and `validate` compute on demand and print (Q14).
- Token or spend accounting against operator CLIs: the source cap and per-source timeout bound a run instead (Q20).
- Query with citations and file-back; deliver/arrangements (roadmap PRDs).
- kiro/copilot adapters (follow-up PRD; the abstraction is designed for them, claude ships first).
- Any integration with ~/bim (permanent non-goal; the human is the bridge).
- Capture tooling (clippers, URL fetchers); sources arrive as files.
- CLI self-upgrade mechanics: the buvis-gems updater (`buvis.pybase.updater`) owns version check, installer detection, and upgrade; klyreon only refreshes its operator assets.
- Obsidian dependency, web UI, multi-vault, team features, publishing.

## Constraints
- Ships as buvis-gems tool 17 (`src/tools/klyreon/`, Click CLI on the `buvis.pybase` shared library): Python 3.11+ managed with uv, gems repo conventions (master branch, conventional commits, CHANGELOG), gems release pipeline and updater.
- Vault discovery config at `~/.config/klyreon/config.yaml` (spec section 10, respects `$XDG_CONFIG_HOME`): vault root, the root-discovery contract for any tool reading the vault, deliberately outside the shared `~/.config/buvis/` resolver. Tool-level settings (auto-update, backend selection, maintenance thresholds) use the gems resolver.
- Operational state (last maintenance run, installed-asset manifest) lives in `$XDG_STATE_HOME/klyreon/`; the Markdown+YAML-only rule below governs vault content, not tool state (gems precedent: `~/.config/buvis/updater.json`, bim's `$XDG_STATE_HOME/bim/doc`).
- Data layer is plain Markdown + YAML frontmatter only; no databases, no custom serialization.
- The vault is expected to be a git repository the user owns; klyreon commits into it but never creates it, and degrades when it is absent: warn, and refuse autonomous mutation (ingest and maintain; init, validate, status, new still work).
- LLM access exclusively through operator CLIs (claude/kiro/copilot), never raw API keys in the product.
- No daemon; autonomy via external scheduler (cron/launchd) driving idempotent commands. Idempotence over persistent workflow state (re-run on failure).
- Semantic work (paraphrase, claims, doubts, contradiction judgment) delegated to the agent backend; everything deterministic stays in CLI code.
- Anti-patterns from `docs/reference/klyreon/lessons-from-prior-iterations.md` are binding unless a design doc argues otherwise.

## Codebase Context
- **Home**: buvis-gems tool 17 at `src/tools/klyreon/` in `/Users/bob/git/src/github.com/buvis/gems` (scaffolded by `dev/bin/scaffold.py`, wired through `pyproject.toml` `[project.scripts]` and wheel packages, enforced by `dev/bin/check_tool_wiring.py`). The founding docs already moved here from the standalone `buvis/klyreon` repo, which is now empty and awaiting archival.
- **Conventions source**: buvis-gems itself - `src/tools/<name>/{cli.py,settings.py,commands/,manifest.toml}`, `CommandResult`, `GlobalSettings`/`ConfigResolver`, a `tests/tools/<name>/` mirror, and `buvis.pybase.updater` for self-update. `pidash hooks install` (`src/tools/pidash/commands/hooks/install.py`) is the working precedent for idempotent, ownership-tracked installation into another tool's directory - it strips its own marked entries and rewrites them, with no hash tracking and no backup, so klyreon extends the pattern rather than copying it (Q18).
- **Foundation contracts** (all under `docs/reference/klyreon/`): `zettel-format-specification.md` (canonical, autonomy-reworked, knowledge-core types, XDG config, audit-002 fixes), `original-karpathy-idea-proposal.md`, `ancient-philosophy-applied-to-zettelkasten.md`, `lessons-from-prior-iterations.md`, `anti-example-prior-build-output.md` (non-normative, measurable ingest-quality floor).
- **Historical quarry (non-binding, in bim project dir)**: old system-architecture.md (operations detail), 800-zettel corpus (possible sanitized fixtures later), test-01 output (quality baseline).

## Approach
- **Chosen**: self-contained Python CLI that orchestrates the full loop itself, invoking pluggable agent-CLI backends (claude first, kiro/copilot next) for semantic operations, and shipping operator-specific assets per backend. Cron/launchd triggers the unattended run: pending-source ingest from `sources/` (bounded per Q20), then maintain - exact invocation shape decided in design; contradiction detection runs inside every ingest.
- **Why**: single artifact owns autonomy (cron-able without an agent harness deciding anything), while agent CLIs supply LLM tooling/auth without API plumbing in the product; deterministic/semantic split follows the code-first rule.
- **Rejected alternatives**:
  - Toolbelt-only CLI with agent skills orchestrating: rejected by owner - the loop must be klyreon's, not the operator's.
  - Raw LLM API integration: provider coupling, key and prompt management inside the product, duplicates operator-CLI capabilities.
  - Built-in scheduler daemon: highest-complexity component with the failure modes attempt #1 died of; external scheduler chosen instead.

## Success Criteria
1. **Unattended ingest**: a source file dropped into `sources/` becomes spec-valid zettels (claims, doubts, links, MOC anchors populated) with zero human interaction, demonstrated across all four spec source types - article, book, quote, transcript (spec 6.1) - from a mixed corpus from day one.
2. **Contradiction surfaces**: each of at least five crafted fixture sources (one per conflict shape plus edge cases) conflicting with an existing accepted claim resolves at ingest into exactly one of the three shapes (spec 8) - aporia (targeted `disagreement` doubts, `contradicts` links, optional aporia zettel), refine (`narrower-than`), or supersede (`supersedes` + loser to `assent: rejected`) - never silent coexistence, on three consecutive runs of the whole fixture set.
3. **Pruning holds the line, on request**: with pruning left at its default, a maintain run over backdated fixtures deletes nothing and lists exactly the expected candidates in its trail entry and in `status`; with pruning enabled in config, the same run removes them, cleans inbound links, and the vault validates clean afterwards.
4. **Autonomy soak**: a cron-driven run of at least 7 days over a mixed corpus completes with zero human input, `klyreon validate` stays clean, no run hangs (the per-source timeout holds), and `klyreon status` reports links per zettel and promotion count at start and end with both increasing (the richer-not-bigger proxies). The corpus must be seeded so at least one claim reaches its second corroboration inside the window.
5. **Failure is invisible in the vault**: a source whose backend call is killed mid-ingest leaves no zettel, no partial trail, no archive move, and no resume state; the next run re-processes it cleanly. An interrupted maintain run leaves the vault `validate`-clean.
6. **Quality floor**: ingesting the anti-example's source material produces zettels that pass a rubric derived from `anti-example-prior-build-output.md` (atomic one-idea notes within the size ceiling, contentful claims rather than summaries, frontmatter links not hand-rolled navigation, no dangling citations); rubric fixed during create-prd.

## Risks
- **Backend claim/judgment quality varies**: contradiction detection is only as good as the operator LLM. Mitigation: fixture-based eval suite per backend; claude first; criteria 1-2 gate release.
- **Pruning deletes good material**: report-only by default, so deletion requires an explicit opt-in; 365-day window when enabled, dry-run report mode, git history as recovery, `rejected` and `delivered-as` exemptions, and no pruning at all in a non-git vault.
- **Noise accumulates instead** (the cost of the report-only default): `status` surfaces the candidate count on every invocation so the backlog stays visible rather than silent.
- **A hung operator CLI wedges the schedule**: per-source wall-clock timeout, and staged writes mean the abandoned source leaves nothing behind.
- **Trail files accumulate**: one per run, forever, in a vault whose pruning is off by default. Retention rule is an open question; the files are small and git-tracked.
- **Missing scheduler silently stops maintenance**: staleness warning on every invocation; `init` installs the schedule.
- **Agent CLI interface drift** (flags/behavior change across claude/kiro/copilot releases): thin adapter layer isolates each backend; pin known-good versions in docs.
- **Claim-set outgrows context** (~5-10k notes): known ceiling, sharding/per-MOC indexes deferred until real scale.
- **Ingest cost**: multiple LLM calls per source; bounded by the Q20 run bounds (max-sources-per-run cap, per-source timeout).

## Open Questions (for create-prd / design)
- Backend contract mechanics: how klyreon passes work to each operator CLI (headless flags, prompt files, output parsing).
- MOC and trail file formats: the trail candidate shape is noted in the lessons doc, and trails now carry run journals (Q14). Does a journal file validate as the spec's trail species, and what frontmatter does it need?
- Trail retention: one file per run accumulates forever in a vault whose pruning is off by default (Q19). Cap by count, by age, or leave to git.
- Claim-set export serialization and destination: Markdown, YAML, or JSON, and stdout vs `$XDG_STATE_HOME/klyreon/` - writing it inside the vault would break the Markdown-knowledge-only rule.
- Staging mechanics for atomic ingest (Q16): where the staging area lives, and how the commit behaves when the working tree already holds uncommitted human edits.
- Default values for `max-sources-per-run` and the per-source timeout (Q20).
- Voice configuration: file location and format (referenced by spec 11.5, owned by ops design).
- Search plumbing for v1: claim-set + rg likely sufficient; qmd integration deferred until scale demands.
- Operator asset install mechanics: per-operator target paths and formats (Claude skills/plugins, Kiro steering, Copilot instructions) and the manifest format under `$XDG_STATE_HOME/klyreon/`, which also records the installed schedule (Q17) and asset hashes (Q18). `pidash hooks install` is the working precedent.
- Spec edits this elicitation requires: 2.1/3.2 archive semantics (Q15), 3.1/10.2 trail purpose (Q14), 7.3 pruning as opt-in (Q19).

## PRD Decomposition (decided)
Three sequenced PRDs: (1) core plumbing - land klyreon as buvis-gems tool 17 (scaffold, wiring, CI), spec engine, validate, init, IDs, claim-set export with assent metadata, and the git commit layer both later PRDs depend on; (2) ingest + backend abstraction with claude as first operator, including atomic staging, archive-first citation, run bounds, and the trail journal; (3) autonomous maintenance + `klyreon schedule` + report-only pruning. The operator-asset install/refresh framework (init selection, manifest, refresh, drift warning) rides with PRD 2; split it out if PRD 2 outgrows one buildable spec. init builds incrementally: PRD 1 ships skeleton + config + git warning; the operator-asset offer joins with PRD 2, the schedule offer with PRD 3. Follow-up PRD: kiro/copilot operator asset packs. Roadmap: query, deliver.

## Discovery Log

### Q0: settled during the founding-docs review (2026-08-05)
- Canonical format spec = newer revision, reworked for autonomy (commits 55c9c14, 88ca850, 2af111b, cb55c10).
- Tag namespaces and `belief` concept-type removed; `claims` MUST on assertion-bearing zettels; pruning and rule-driven assent/lifecycle added.
- Queued into elicitation: type-vocabulary scope; config location; relation-seeking mandate; self-triggering maintenance; MOC/trail format; archive-path timing.

### Q1: Where does the LLM sit relative to the klyreon CLI?
**Answer**: Self-contained CLI (option 2): klyreon orchestrates the whole loop and invokes LLM operators itself - pluggable agent backends, mainly **claude (Claude Code), kiro, and copilot**. Part of the product is shipping operator-specific assets (skills, rules, possibly custom agents) for each backend; understood as part of the design phase. Mechanical work stays in deterministic CLI code; semantic work is delegated to the configured agent backend.

### Q2: Which operations must v1 support end-to-end?
**Answer**: Ingest with contradiction detection, and autonomous maintenance (self-triggered lint, promotion, assent transitions, pruning). Query and deliver go to the roadmap. Basics (init, validate, new-zettel, search/index) are implied plumbing.

### Q3: What is the primary corpus at launch?
**Answer**: Mixed from day one - articles, short-form, transcripts, books/papers all first-class. Accepted trade-off: acceptance criteria must span source types rather than optimize one.

### Q4: Zettel type vocabulary scope?
**Answer**: Knowledge core only. Source types (article, book, quote, transcript) + 8 knowledge zettel types (note, definition, procedure, wiki-article, cheatsheet, snippet, course, ai-prompt). Work, config, lists, personal-life clusters dropped - that content stays in bim. Utility/concept distinction survives. Spec edit applied (commit 41af6a3).

### Q5: Implementation stack?
**Answer**: Python 3.10+ managed with uv, matching the buvis ecosystem. Single-binary distribution traded away for iteration speed.

### Q6: Config location?
**Answer**: XDG - `~/.config/klyreon/config.yaml` (vault root, backend selection, maintenance thresholds). Spec edit applied (commit 41af6a3).

### Q7: How does autonomous maintenance trigger in v1?
**Answer**: External scheduler - `klyreon maintain` is idempotent, scheduled via cron/launchd (installed by setup docs or `klyreon init`). Staleness warning on every invocation covers a missing schedule. No daemon; contradiction detection runs inside every ingest.

### Q8: Which success criteria must v1 be held to?
**Answer**: All four - unattended ingest across source types; contradiction surfaces on a crafted fixture; pruning removes stale material cleanly; multi-day autonomy soak stays clean with richer-not-bigger proxies moving.

### Q9: How should v1 be cut into PRDs?
**Answer**: 3 sequenced PRDs (core plumbing; ingest + claude backend; maintenance + scheduler), kiro/copilot adapters as follow-up. Contradiction check across all answers: none found.

### Q10: User-added requirement (post-elicitation)
**Requirement**: klyreon must install the operator asset files (skills, rules, steering, agent definitions) for the agents the user selects - likely as part of `init` - to simplify user setup. Because klyreon updates may change those files, a self-update path must refresh installed assets too: manifest-tracked installs, refresh on update, drift warning. Proper solution to be designed in the design phase.

### Q11: Where does klyreon live? (decided during discovery review, 2026-08-05)
**Answer**: buvis-gems, as tool 17 - not a standalone repo. Gems already ships the generic updater klyreon needed (`buvis.pybase.updater`: PyPI check, installer detection for uv-tool/pipx/mise/pip-venv, delegated upgrade, re-exec, `--update` flag on every tool), the PyPI release pipeline, the config/console/`CommandResult` plumbing, and `pidash hooks install` as a working template for installing owned files into another tool's directory. Consequences accepted: Python 3.11+ (gems floor) instead of 3.10+, releases ship all 17 tools together, and klyreon's code sits beside `bim` and `pybase.zettel` - code proximity only, the `~/bim` vault non-goal is unchanged. Vault-root config stays at `~/.config/klyreon/config.yaml` per spec 10; only tool settings use the gems resolver.

### Q12: Does klyreon own the vault's git repository, and does it commit its own writes? (2026-08-06)
**Answer**: Commits only, never inits. The user creates the repo; klyreon commits its own writes under a klyreon identity, so git authorship cleanly separates machine commits from human ones. Klyreon warns when the vault is not a git repo. Rationale: the user keeps control of history, remotes, and gitignore.
**Implication (assumed, flag for design)**: pruning is the only operation that destroys data, so `maintain` skips pruning in a non-git vault (warn and continue) rather than deleting files with no archive behind them.

### Q13: What does the claim-set export carry alongside each claim statement? (2026-08-06, closes audit 002 G6)
**Answer**: Claim id and statement plus the parent zettel's `assent`, `lifecycle`, and root-relative path. Rejected claims stay in the export but arrive labelled, so the detector separates "conflicts with a claim the vault endorses" (a real conflict, resolve into aporia/refine/supersede) from "conflicts with a claim the vault already refused" (corroborates the rejection, no new aporia). Rejected doubts/aporia back-references were considered and dropped as speculative until duplicate aporias are actually observed.

### Q14: Does v1 write trails, and where does the record of each autonomous run land? (2026-08-06, closes audit 002 G4)
**Answer**: Trails become the autonomous-run journal. Every ingest and maintain run writes one trail file (`wiki/trails/YYYYMMDDHHmmSS.md`, spec 3.1 naming) recording sources ingested, zettels created, each conflict and the shape it resolved into, prunes, and promotions. The human reads what the machine did without digging through git log, and roadmap query sessions later write the same shape. `index.md`, `log.md`, `lint-report.md` and `arrangements/` stay out of v1: `status` and `validate` compute on demand and print. Trail files need their own retention rule eventually (noted as an open question).

### Q15: How does v1 resolve the source-archive path timing? (2026-08-06, closes spec 3.2 open question)
**Answer**: Archive-first ingest. Ingest resolves the archive path up front and every derived zettel cites `sources/archive/YYYY-MM/...` from birth: no dangling paths, no rewrite pass, validator stays strict with no two-location fallback. Accepted cost: "archived" now means "ingest committed", not "zettels approved by a human" - spec 2.1/3.2 wording needs the edit. Refined by Q16: the physical move is part of the atomic commit, so a failed ingest leaves the source in `sources/YYYY-MM/` and nothing dangles. Spec edit required.

### Q16: What state does the vault land in when a backend call fails mid-ingest? (2026-08-06)
**Answer**: Stage, then commit all or nothing. New zettels, conflict edits, the source move, and the trail file are built in a staging area and applied to the vault only when the whole source succeeds; on failure nothing lands and the source stays in the inbox. Keeps idempotence without persistent workflow state, at the cost of re-doing backend work on retry. Interaction with Q15: because the archive move is part of the staged set, a failed ingest leaves the source in `sources/YYYY-MM/`, not in the archive.

### Q17: How much of the scheduler installation does klyreon automate? (2026-08-06)
**Answer**: A dedicated `klyreon schedule install|status|uninstall` subcommand, offered by `init`. It writes a launchd plist on macOS and a crontab line on Linux, records what it wrote in the same manifest that tracks operator assets, and can be re-run after a machine change without touching the vault. Adds `schedule` to the v1 command surface (7 commands). Accepted cost: two platform backends, and the usual scheduler traps (PATH inside cron, launchd label collisions) need test coverage.

### Q18: What happens on refresh to an operator asset the user has edited? (2026-08-06)
**Answer**: Back up, then overwrite. The manifest records a content hash at install; refresh compares, saves the user's version beside the file when it differs, writes the current asset, and reports every displaced file. Klyreon-owned assets stay correct and no edit is destroyed silently. Accepted cost: backup files accumulate in the operator's directory and the user re-applies tuning by hand.

### Q19: What are the shipped defaults for assent promotion and pruning? (2026-08-06)
**Answer**: Pruning is report-only by default. Owner rationale: material stays valuable long after it stops moving ("resources not updated for more than 9 years and we are fine"), so no machine deletes without explicit consent. Maintain lists prune candidates in its trail entry and in `status`; deletion happens only when the owner turns pruning on in config, and the window then defaults to 365 days. Promotion to `accepted` stays at 2 corroborations from different sources. Consequence: the pruning code still ships and success criterion 3 is exercised by enabling pruning on backdated fixtures, not in normal operation.

### Q20: What bounds an unattended run? (2026-08-06)
**Answer**: A `max-sources-per-run` cap (small default; the remainder waits for the next scheduled run) plus a per-source wall-clock timeout. Bounds both the batch and a pathological single source, and keeps the tool cron-safe - a hung operator CLI cannot wedge the schedule. Token/spend accounting was rejected for v1: it needs each operator CLI to report usage in a parseable form, which is drift-prone per-backend work for something the cap already covers. Accepted cost: a timeout discards that source's staged work, so the quota is spent with nothing to show.

### Contradiction check across Q12-Q20
Three conflicts found and resolved, none left open:
- Q15 (archive-first) vs Q16 (all-or-nothing staging): the archive move joins the staged set. Zettels still cite the archive path from birth, and a failed ingest leaves the source in the inbox. Strictly better than either answer alone.
- Q19 (pruning report-only) vs success criterion 3 and the maintain must-have, both of which assumed autonomous deletion: criterion 3 now tests both modes and the must-have splits pruning into detection (always) and deletion (opt-in).
- Q17 (`klyreon schedule` subcommand) vs the v1 command surface, which listed six commands: surface is now seven.

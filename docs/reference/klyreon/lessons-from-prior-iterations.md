# Lessons from Prior Iterations

Non-binding input to Klyreon's requirements. These are the paid-for lessons of the first build (the `zettelmaster` skill generation) and its feedback round, adapted to the reboot's constraints: mostly-autonomous operation, contradiction detection as the primary capability, pruning against information overload, human review never load-bearing. Where a lesson conflicted with those constraints, the adaptation is noted. Nothing here overrides the format spec or the requirements to come.

## Anti-patterns: what attempt #1 did that the reboot rejects

- **Parallel workflow engine.** Thirty-plus Python scripts grew beside the skills into a competing state machine. The boundary rule: semantic work (drafting, interrogating, paraphrasing, assent, doubt) stays with the LLM; mechanical work (parsing, indexing, collision bumping, structural lint) belongs in code. Helpers stay small, single-purpose, and owned by the operation that uses them.
- **Custom serialization.** TOON for "25% token savings" made files unreadable to every other tool. Plain Markdown + YAML frontmatter only.
- **Phase state machines.** Six-phase ingest with checkpoints and resumable workflow state. Instead: each operation runs end-to-end; if it fails, re-run it. Idempotence over persistence.
- **Taxonomy sprawl.** Seventeen relation types produced decision fatigue with no proportional gain (capped at ten in the spec). The reboot finishes the same lesson: a dimension is promoted to frontmatter only when an operation queries it, and the four namespace tag vocabularies (`kind:`/`topos:`/`sphere:`/`output:`) kept "just in case" were removed entirely.
- **Parallel directories for LLM-written vs human-written notes.** Two trees, confusion at every operation. One `wiki/notes/` plus the `processed` flag.
- **Sub-agent orchestration as default.** Five agent types for one pipeline. One tool per operation; parallelism only when a measured need appears.
- **Noise filter as a component.** Dedicated `noise_filter.py` scripts. Filtering is a property of capture (clean clippers) and interrogation (ingest extracts, it does not transcribe), not a pipeline stage.
- **Archive as a system.** Scripts, manifest, and cron for what is one `mv` at the end of ingest.
- **Obsidian dependency.** Recommended viewer, never a requirement; everything must work as plain files.

## Success criteria worth keeping (adapted for autonomy)

1. **Ingest does not block.** A new source yields drafted concept zettels (claims, doubts, links, cross-update applied) with no human interaction required.
2. **Contradictions surface structurally, never silently.** A conflict with existing accepted claims materializes as `disagreement` doubts, `contradicts` links, or an aporia zettel at ingest, or at the next lint pass at the latest.
3. **The wiki gets richer, not just bigger.** Cross-links, promotions, merges, and pruning all happen as it grows; growth without integration means it became an archive.
4. **Pruning works.** Stale, orphaned, uncorroborated fleeting material demonstrably leaves the wiki on schedule; the noise floor does not rise with age. (New criterion - overload control had none in attempt #1.)
5. **When a human does review, it is fast.** Minutes per zettel, and most drafts pass with minor edits; low acceptance signals shallow ingest, not lazy review. (Now conditional - review is opportunistic, never required.)
6. **The phronesis test.** Concept zettels ultimately shape deliverables and decisions; `delivered-as` is the measurable proxy.

## Open questions carried forward

- Claim-set scaling past ~5-10k notes: claim clustering, per-MOC sub-indexes, or nightly full-pass plus write-time top-k. Revisit at real scale.
- Voice drift across months of self-exemplar drafting; how often the voice configuration needs reinforcement.
- Schema evolution: what happens to old notes when the contract changes ("they keep working under old conventions until next touched" is informal and may break non-obviously).
- Maintenance trigger: attempt #1 resolved rework as "human attention is the trigger (daily briefing)". Re-opened - that conflicts with the autonomy constraint; maintenance must self-trigger.
- Image semantics: assets are stored but nothing reads them.
- Multi-base and cross-base query, per-claim review granularity, team variants: all out of v1 scope.

## Requirement seeds from the feedback round

- **Noise filtering style.** Extract facts, ideas, and concepts with extreme concision; sacrifice grammar before meaning; never corporate-presentation prose; keep the maximum of the original signal.
- **Relation completeness.** After ingesting a zettel (and again after its batch), check for missing relations; optionally research externally to close a gap the source left open.
- **Integration over creation.** Prefer updating, linking, or merging into existing material over creating parallel new files.

## Trail format candidate (from the earliest proposal)

The Perplexity-era proposal sketched trails as numbered, timestamped steps that reference zettel IDs, under frontmatter carrying `topic`, `started`/`ended`, and `status: in-progress | complete`. A workable starting shape for the spec's open trail-format question; its interactive "Socratic session" framing and "never auto-commit, always show diffs" rule are superseded by the autonomy constraint.

## Use-case seeds (from the idea era, de-bim-ified)

- Drop an article into `sources/`, run ingest, see every file it touched.
- Periodic lint: contradictions, orphans, concepts mentioned repeatedly without a zettel, claims superseded by newer sources - reported with specific fixes.
- Process a call or meeting transcript into concept zettels linked back to the transcript source.
- Morning digest of what changed and what needs attention. (Attempt #1 framed this as the human review trigger; under autonomy it is a status surface, not a dependency.)

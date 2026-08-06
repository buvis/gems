# Anti-example: what attempt #1 actually produced

Non-normative. This is the paid-for evidence behind the noise-filtering, atomicity,
and format-conformance requirements: the real output of the `zettelmaster` build,
preserved at
`~/bim/reference/local/10-projects/20251111171017-create-documents-into-zettelkasten-claude-skill/test-01-generated-notes/`.

`lessons-from-prior-iterations.md` states the anti-patterns abstractly. This file
makes them checkable. A Klyreon acceptance test for ingest quality should be able to
fail against the specimens below.

## Measured

165 generated files across six topic directories.

| Symptom | Measurement |
|---|---|
| No YAML frontmatter at all | **58 of 165 files** |
| No zettel ID anywhere | all 165 (filenames are `Graph-RAG.md`, `30_kmeans.md`, `02_Caching.md`) |
| Not atomic | `16-rag-types/Graph-RAG.md` is **411 lines, 11 H2 sections** covering architecture, applications, four vendor products, code samples, and a reading list |
| Navigation hand-rolled | `[<- Back to RAG Types Index](./RAG-Types-Index.md)` header and footer instead of links in frontmatter |
| Directory-per-topic | topic hierarchy in the filesystem instead of MOCs |
| Dangling citations | numeric footnote markers (`[7]`, `[15]`, `[76]`) with no resolvable target |

## Specimen A: not a zettel, a link list

`system-design-staircase/02_Caching.md`, verbatim and complete:

```markdown
# Caching

## Definition
Caching is a performance optimization technique for temporarily storing frequently accessed data in a fast-access layer (such as RAM), reducing latency and load on backend systems[7][8][15]. Caching is essential in system design for boosting responsiveness and scalability, but requires careful attention to consistency and invalidation challenges.

## Key Concepts
- In-memory vs distributed vs client-side caching
- Content Delivery Networks (CDNs)
- Database and application caching
- Eviction policies (LRU, LFU, FIFO, etc.)
- Cache coherence and invalidation
- Cache-aside, write-through, and write-behind patterns

## Essential Reading
- [Algomaster: What Is Caching][7]
- [CodeWithVed: Caching Strategies][8]
- [System Design: Caching Strategies][15]

## Further Study Resources
- [System Design Primer][76]
- [Caching (SystemDesignSchool)][16]
```

What Klyreon requires instead: frontmatter with `id`, `title`, `created`, `type`;
one idea, not six bulleted headings; a `claims` entry if it asserts anything; the
sources in `sources`, not in a "Further Study Resources" list; membership in a MOC
rather than a topic directory. As written this file asserts nothing, so nothing in
it can be contradicted, corroborated, promoted, or pruned. It is invisible to every
Klyreon operation.

## Specimen B: corporate-presentation prose

Opening of `16-rag-types/Graph-RAG.md`:

> Graph RAG enhances traditional Retrieval-Augmented Generation by incorporating
> **knowledge graphs**-structured representations of entities and their
> relationships. This approach enables sophisticated multi-hop reasoning, semantic
> understanding, and explainable AI outputs by leveraging the inherent connectivity
> of graph-structured data.

Two sentences carrying one fact. "enhances", "sophisticated", "enables",
"leveraging", "inherent" are the exact register the feedback round banned: *"be
extremely concise and sacrifice grammar. Avoid corporate presentations style at all
costs."*

The same file's "Benefits" section runs four H3 headings of unsourced assertion
("Rich Information Context", "Enhanced Context Handling", "Explainability",
"Reduced Ambiguity") with twelve bullets under them and not one number, citation,
or bounded condition. Under Klyreon every one of those would be either a claim with
a source or cut.

## Specimen C: the near-miss

`ml-algorithms/30_kmeans.md` (70 lines) is the closest any file gets: dense,
concrete, no marketing register, real formulas. It still fails on structure - no
frontmatter, no ID, no links, no claims - and it is a textbook section rather than
an atomic idea. It is the useful reminder that fixing the prose style alone does
not produce a zettel.

## What this evidence supports

1. **Format conformance must be mechanically validated, not requested.** 35% of a
   supervised run produced files with no frontmatter. A CLI that writes zettels must
   validate before it writes, and lint must reject non-conformant files it finds.
2. **Atomicity needs an enforced ceiling.** "One zettel, one idea" produced a
   411-line file. The ingest operation needs a concrete split rule, and lint needs
   an oversized-zettel check.
3. **Noise filtering is an output criterion, not a pipeline stage.** The prior build
   had two dedicated noise-filter scripts and still shipped Specimen B.
4. **A zettel that asserts nothing is inert.** Specimen A is the argument for
   `claims` being MUST on assertion-bearing shapes: without them the compounding
   machinery has no substrate.

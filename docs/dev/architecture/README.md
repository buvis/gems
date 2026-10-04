# Architecture

Maintained overview of the buvis-gems system: its components, boundaries,
interfaces and load-bearing invariants. Update these documents when an
implementation change alters the system they describe.

The authoritative, always-on invariants live in the root [`AGENTS.md`](../../../AGENTS.md)
("Invariants (evolution guardrails)"). This directory holds the longer-form
rationale behind them.

## System overview

buvis-gems is a single PyPI package (`buvis-gems`) bundling a shared internal
library (`buvis.pybase` + the zettel subsystem) and a family of CLI tools under
`src/tools/`. See the root `AGENTS.md` "Architecture" section for the directory
map and the key packaging/namespace patterns.

## Documents

- [`all-interface-architecture.md`](all-interface-architecture.md) — the
  all-interface seam: one action, one implementation across CLI/TUI/API/WebUI,
  wired through each tool's composition root and returning `CommandResult`.
- [`bim-doc-architecture.md`](bim-doc-architecture.md) — the `bim doc` document
  processing and library-management subsystem.

## Decision records

Significant architecture decision records live in [`decisions/`](decisions/).
Each records context, decision, status and consequences; superseded records are
retained with links to their replacements.

A change's historical design stays in its spec bundle
(`../project-management/specs/NNNNN-title/design.md`). This overview describes the
*current* system; decision records retain enduring rationale.

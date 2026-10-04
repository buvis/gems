# Agent host-support capability table

Realizes decision 11 ("Shared instructions with explicit host support") of the
AI-age repo-structure design. This is the **shared capability table** that
records, per host, the entry point used to load buvis-gems' authored
instructions, the host's nested-`AGENTS.md` behavior, any required adapter or
fallback, and the evidence behind each claim.

The design mandates two distinctions this table keeps honest:

- **Enabled surfaces only.** We record the hosts buvis-gems actually integrates
  with, not every brand that supports `AGENTS.md`. A brand name alone is not a
  support claim. Hosts not committed to the repo are listed under *Not enabled*.
- **Documentation evidence ≠ installed-version probe.** A documented loading
  behavior and a probe of the version installed here are separate facts. An
  adapter is advertised as *working* only when a probe confirms it; otherwise it
  is *documented* (doc-only) or *unverified*.

## Enabled surfaces

buvis-gems commits exactly two authored-instruction sources:

- Root [`AGENTS.md`](../../../AGENTS.md) — the canonical prose-steering source.
- [`CLAUDE.md`](../../../CLAUDE.md) — a one-line `@AGENTS.md` import bridge
  (decision 8), plus optional Claude-only notes that defer to `AGENTS.md` on
  conflict.

No `.cursor/`, `.codex/`, `.github/copilot-instructions.md`, or committed
`.kiro/` adapter exists in the repo, and none is planned (decisions 10/11): the
goal is one authored source reached by native discovery or the smallest pointer.

## Capability table

Probe evidence below was collected on **2026-10-04** on the maintainer's macOS
box by running each agent's `--version`. Documentation evidence is dated where it
differs. A probe confirms the binary and version present here; it does **not**
certify every CLI/IDE/cloud surface that ships under the same brand.

| Host | Entry point into gems' instructions | Nested-`AGENTS.md` behavior | Adapter / fallback | Evidence |
|---|---|---|---|---|
| **Codex CLI** | Native: startup chain walks project root → working directory, reading `AGENTS.md` at each level. | Documented as loaded along the root→cwd chain. Files **outside** that chain need the agent-followed read fallback (below). | None required. Root `AGENTS.md` is read natively. | **Probed** `codex-cli 0.160.0` (2026-10-04). Doc: [Codex instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md). |
| **Claude Code** | `CLAUDE.md` `@AGENTS.md` import bridge. Native `AGENTS.md` support depends on version/settings. | **Unverified** on the installed version: whether Claude auto-loads a *nested* `src/.../AGENTS.md` on its own is not confirmed. The import bridge pulls only the root file. | Keep the `CLAUDE.md` import bridge (adapter owner: this repo, hand-authored). For nested files, rely on the read fallback until native nested discovery is verified for the pinned version/settings. | **Probed** `2.1.289 (Claude Code)` (2026-10-04). Doc: [Claude Code memory](https://code.claude.com/docs/en/memory). |
| **Copilot CLI** | Not currently wired. Copilot support varies by surface (CLI vs IDE vs GitHub features) and entry point. | Not applicable until a surface + entry point is chosen and its minimal adapter added. | Would require recording the exact surface and its supported entry point, then adding only that minimal adapter — not enabled today. | **Probed present** `GitHub Copilot CLI 1.0.91` (2026-10-04), but **not integrated**. Doc: [Copilot custom-instructions support](https://docs.github.com/en/copilot/reference/custom-instructions-support). |

### Not enabled (documentation-only, no local probe)

| Host | Documented behavior | Why not enabled |
|---|---|---|
| **Cursor** | Walks the directory tree for `AGENTS.md`. | Binary **absent** on the maintainer's box (no `cursor`/`cursor-agent` on PATH, 2026-10-04); no committed adapter. Add only when actually used. |
| **Kiro editor** | Nested `AGENTS.md` documented as always included; custom-agent steering resources need explicit configuration. | Not integrated. Note: `~/.kiro/` existing is **not** a Kiro-editor signal (it is also KiroCrew's config root) — detect by the Kiro binary on PATH or a Kiro-specific marker, never directory existence. Doc: [Kiro steering](https://kiro.dev/docs/steering/). |

## Nested-`AGENTS.md` discovery and the agent-followed fallback

Decision 11 requires the root instructions to tell an agent to **discover and
read** applicable nested `AGENTS.md` files before working on the files they
govern, on any host that has not already loaded them. This is a documented
agent-followed fallback — **not** equivalent to automatic native loading, and it
is recorded separately here from native discovery.

Current state in buvis-gems:

- There is **one** `AGENTS.md` today — the root file. No nested `src/<module>/AGENTS.md`
  exists yet, so the fallback is currently moot but will apply the moment one is
  added.
- The root `AGENTS.md` does **not yet** carry the "discover and read applicable
  nested `AGENTS.md`" instruction. Adding that sentence is the prerequisite for
  relying on the fallback on Claude Code (whose native nested loading is
  unverified) and for any file outside Codex's root→cwd chain. **Follow-up:**
  add the discovery/fallback instruction to root `AGENTS.md`, and give every
  future nested file an explicit directory-scope line (required even on hosts
  that load it eagerly).

## Maintenance

- Re-probe versions when an agent is upgraded; update the evidence date.
- When a new host surface is enabled, narrow its row to the exact surface and
  entry point, record the version/settings, name the adapter's owner, and state
  any fallback limitation. Do not advertise an adapter as working on
  documentation alone.
- Skill discovery (Braid projection) and the Kiro spec-panel link have their own
  verification gates; working instruction loading does not establish either.

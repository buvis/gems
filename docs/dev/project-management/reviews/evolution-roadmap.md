# buvis-gems Evolution Roadmap

**This file is the ordering authority.** Autopilot drains `dev/local/prds/backlog/` lowest-number-first, so the sequence numbers below *are* the execution order. Every PRD's dependencies point only at lower numbers — verified. Evidence and rationale live in `evolution-assessment-2026-07-09.md`.

Generated 2026-07-09. All PRDs are scoped to one implementation session.

## Phases

| Phase | Theme | PRDs |
|-------|-------|------|
| **P0** | Stop the bleeding: data-loss + Critical security | 00041–00045 |
| **P1** | Correctness / convergence | 00046–00050 |
| **P2** | Leverage: finish the all-interface seam | 00051–00055 |
| **P3** | Enablement + top user wins | 00056–00059 |
| **Hygiene** | Deletion / librarization | 00060–00061 |

## The one root cause

The all-interface goal (CLI/TUI/API/WebUI parity) already has a **proven seam** — bim's `ACTION_HANDLERS` registry + command classes + `bim/dependencies.py` composition root. It is just not *mandatory*, so dot's TUI and parts of bim's serve/TUI reimplement logic instead of consuming it. Finishing and enforcing that seam (P2) is the highest-leverage work: it ends the duplication that the commit history shows breeding 6× the fix density in the ad-hoc TUIs. **P0/P1 buy safety; P2 buys cheap future interfaces.**

## Ordered PRD list

### P0 — data-loss + critical security (do first, any order among themselves)

- **00041 · atomic-write foundation** — lift `atomic_write_text/bytes` into `pybase/filesystem/`; make `MarkdownZettelRepository.save` atomic (THE note-save data-loss path); fix `updater/state.py` (silently non-atomic). *Foundation for 00049, 00056.*
- **00042 · bim serve confinement + auth** — confine every path param to vault+archive; add `TrustedHostMiddleware` + loopback assertion + local token. Critical.
- **00043 · bim doc promote collision** — reuse ingest's seconds-increment resolver; never overwrite an archive PDF/zettel.
- **00044 · bim doc claim/dedup integrity** — release claim on `BaseException` (try/finally) + claim TTL + record source sha on triage/promote.
- **00045 · dot rm safety** — encrypted rm untracks (keeps plaintext) instead of destroying both copies; `shlex.quote` the filename (injection).

### P1 — correctness / convergence

- **00046 · dot TUI secret-status refresh** — fix #92; hide secrets before porcelain in `GitOps.status()`. *(Its code is later subsumed by 00053; ship the fix now.)*
- **00047 · updater fail-loud** — re-exec failure → stderr + nonzero exit; drop/raise the 120s upgrade timeout.
- **00048 · fctracker integrity** — assert CSV date monotonicity (wrong order → wrong money); catch overdraft/bad-row in the command layer.
- **00049 · pidash hook durability** — `flock` around state.json RMW; fsync-before-replace (#111); install ordering (#112); close #113/#114. *(Depends on 00041 helper.)*
- **00050 · zettel scanner error surfacing** — surface dropped `_errors`; align Python-fallback semantics with Rust.

### P2 — leverage: the all-interface seam

- **00051 · all-interface seam design** *(decision/spike, produces `dev/local/specs/all-interface-architecture.md`, no product code)* — names the registry seam, the result-mapping-per-transport, the exemplar, the parity checklist. **Gates 00053, 00054, 00057.** `design_gate: user`.
- **00052 · decouple pybase from Click** — install the parse-args patch inside `buvis_options` (not at import time); route uv/updater output through the console adapter; stop re-exporting Click glue from `configuration/__init__`. Lets headless (API/WebUI/TUI) processes load settings. *(Independent of 00051; sequenced here.)*
- **00053 · dot git-ops unification** — one shared git-ops service (non-interactive, injected shell + `dotfiles_root`, returns `CommandResult`); CLI + TUI both consume it. Subsumes 00046's area. *(Depends on 00051.)*
- **00054 · bim serve + TUI convergence** — PATCH route → `UpdateZettelUseCase`; action handlers return `CommandResult.to_dict()` + real HTTP status; WebUI checks the envelope (fix success-on-failure); TUI create → `CommandCreateNote`; screens surface `CommandResult` failures. *(Depends on 00051.)*
- **00055 · bim cli.py modularization** — split the 773-line registry into per-group Click modules; split `test_cli.py`; adopt `console.report_result`.

### P3 — enablement + user wins

- **00056 · bim doc migrate-layout** — ship the promised legacy-zettel migration (dry-run default, atomic rewrite, per-file skip-and-report). *(Depends on 00041.)*
- **00057 · bim doc triage review** — `bim doc triage` list + `--approve`; register as a serve action via the 00051 seam. *(Depends on 00051; verify queue is non-trivial first.)*
- **00058 · dot diff-layout extraction** — pure `DiffLayout` model (hunk→offset, clamping, visible-region) unit-testable without Textual; widget only renders. Ends the scroll-math bug class.
- **00059 · pidash state-schema contract** — versioned pydantic state model shared/contract-tested with the autopilot skill; Textual snapshot tests as the default layout-change gate. Ends the pidash TUI churn.

### Hygiene — deletion / librarization

- **00060 · delete dead code** — `adapters/uv` + `hello_world` tool + `configuration/examples/` (~1,240 LOC, all test-backed dead weight).
- **00061 · prune formatting + relocate suggest_tags** — dead formatting surface down to the 4 live methods; move the Ollama client out of the formatting package into bim.

## Opportunistic (not queued — do when next touching the file)

Low-severity, no user impact; jumping the queue isn't worth it. Extract as you pass through:

- Collapse `ZettelReader`/`ZettelWriter`/`ZettelRepository` (3 ABCs, 1 impl) to one `ZettelRepository` seam; retype `query_zettels_use_case.py:29`.
- Fold `QuantifiedItem` ABC into `Deposit` (fctracker; 26 LOC, 1 impl).
- `DocValidationError(ValueError)` subclass for bim doc's 67 bare `ValueError` raises + broad catches.
- `buvis_model_config(prefix)` factory for the 15 identical `SettingsConfigDict` blocks.
- Replace bare `console.panic(str(exc))` exception dumps (`bim/cli.py:197,254,606,667,708`; `netscan/cli.py:32,54`; `outlookctl/cli.py:35`) with real messages.
- `chmod 0600` on the readerctl/readwise token file (`login.py`), and validate-before-write.

## Dependency check (no PRD depends on a higher number)

- 00049 → 00041 ✓ · 00053 → 00051 ✓ · 00054 → 00051 ✓ · 00056 → 00041 ✓ · 00057 → 00051 ✓. All others: no cross-PRD dependency.

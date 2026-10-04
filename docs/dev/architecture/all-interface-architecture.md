# All-interface architecture: the seam

Status: **accepted** (reviewed attended by Bob, 2026-07-10; replaces PRD 00051, now in `dev/local/prds/hold/`).
Consumers: 00053 (dot git-ops), 00054 (bim serve/TUI convergence), 00057 (doc triage actions), 00055 (report_result adoption). Every future multi-interface change follows it.

## Decision

One action, one implementation: **command classes (or a domain service) returning `CommandResult`, wired through the tool's composition root, are the seam.** Every interface — CLI, TUI, API, WebUI — is a thin adapter that builds params, invokes the same command, and maps the `CommandResult` per the transport table below. The **action registry** is the dynamic-dispatch adapter over those commands; it is mandatory for every name-based transport (API `POST /actions/{name}`, WebUI action bars, TUI action bars driven by query YAML), and not required for statically wired transports (Click commands, TUI key bindings), which bind to the same command classes directly. Interface adapters never contain business logic.

The AGENTS.md all-interface rule reads per-tool: an action must work identically across **the interfaces its tool ships** (bim: CLI+TUI+API+WebUI; dot: CLI+TUI; everything else: CLI), not "every tool grows four interfaces".

## The seam, concretely

**Command class contract** (exemplar: `bim/commands/*/`):
- Frozen params object in `bim/params/` (dataclass/pydantic).
- Constructor takes injected ports (repo, formatter, shell, ...) from the composition root — never constructs adapters itself, never mutates `os.environ`.
- `execute() -> CommandResult` (`buvis.pybase.result`): `success`, `output`, `error`, `info`, `warnings`, `metadata`. All outcomes are values — no `console.*`, no `sys.exit`, no raw exceptions for control flow.
- Verb-style tools may use a domain service instead (00053's `DotGitService`): mutation methods return `CommandResult`, queries return typed data. The service is the seam; CLI command classes and TUI screens are its adapters.

**Composition root** (exemplar: `src/tools/bim/dependencies.py`):
- One module per tool of `get_*()` provider functions with lazy imports (keeps optional extras optional).
- Every interface obtains ports only from here. dot gets the same shape when 00053 lands (`ShellAdapter` + `dotfiles_root` injected, not env-mutated).

**Action registry** (exemplar: `src/tools/bim/commands/serve/_actions.py`):
- `ACTION_HANDLERS: dict[str, ActionHandler]`, `ActionHandler = Callable[[file_path: str, args: dict, AppState], Coroutine[..., dict]]`.
- Target handler shape (00054): build params from `(file_path, args)` → run the command class via the composition root → `return result.to_dict()`. Nothing else — a handler that grows logic is a defect; move the logic into the command.
- Dispatched by the generic route `POST /api/actions/{action_name}` (`_routes.py:198-204`); unknown name → 404.
- Query YAML `actions:` blocks (`ActionSpec`: name/label/scope/handler/args/confirm, `query_spec.py:103`) reference registry names — adding a WebUI/TUI action-bar entry is YAML, not Svelte.
- One registry per tool, living with its serving transport (bim: `serve/_actions.py`). A tool without a name-based transport (dot today) has no registry.

## Result mapping per transport

| Transport | Mapping | Exists? |
|---|---|---|
| CLI | `console.report_result(result, ...)` renders info/warnings + success/failure; the CLI layer exits non-zero on failure (`console.panic(result.error)` when the command is the primary operation) | exists (`console.py:242`); adoption in 00055 |
| API | handler returns `result.to_dict()`; the generic route reads the envelope's `success`: `True → 200`, `False → 422` (envelope body either way). 401/403/400 belong to the 00042 security layer (`X-Buvis-Token`, `confine_path`, TrustedHost) and fire **before** the handler; 404 = unknown action | `to_dict` exists (`result.py:41`), zero callers; wiring in 00054 |
| TUI | `notify_result(result, notify)` — **new** pure helper in `buvis.pybase.result`: `def notify_result(result: CommandResult, notify: Callable[..., None]) -> None`. Failure → `notify(result.error, severity="error")`; warnings → `severity="warning"`; success with output → `severity="information"`. Takes the `notify` callable as a parameter so pybase never imports Textual (lib stays interface-agnostic) | to create in 00054 |
| WebUI | `api.ts` types the envelope (`success/output/error/info/warnings/metadata`), checks `res.ok` **and** `success`; on failure surfaces `error` (ActionBar shows failure feedback). Requests carry `X-Buvis-Token` (00042) | to create in 00054 |

## Parity checklist: add one action to bim

1. **Logic**: `src/tools/bim/commands/<action>/<action>.py` — command class returning `CommandResult`; params in `bim/params/<action>.py`.
2. **Ports**: new providers in `bim/dependencies.py` only if the command needs a new port.
3. **CLI**: the owning command-group module registers the Click command → builds params → runs the command → `console.report_result`.
4. **API + WebUI**: async handler in `serve/_actions.py` + one `ACTION_HANDLERS` entry; expose to users via an `actions:` entry in the relevant query YAML. No Svelte changes for standard actions.
5. **TUI**: screen binding/action-bar entry → same command class → `notify_result`.
6. **Tests**: command unit test + TestClient test on `POST /api/actions/<name>` asserting 200-on-success and 422-with-envelope-on-failure.

For dot (CLI+TUI): steps 1–3 and 5 against `DotGitService`; no registry until dot grows a name-based transport.

**The rule**: if adding an action requires writing the same behavior twice, the seam has been bypassed — stop and fix the adapter instead.

## Migration order (existing drift → seam)

1. **00053 dot** — furthest from the seam: three parallel git layers (`commands/*`, `tui/git_ops.py`, `tui/commands/{browse,secrets}.py`) collapse into `DotGitService`; CLI and TUI become adapters. No registry.
2. **00054 bim** — serve PATCH route stops writing inline (delegates to `UpdateZettelUseCase`, keeping the 00042 security layer); handlers return `result.to_dict()` + 200/422 mapping; TUI create goes through `CommandCreateNote`; screens adopt `notify_result`; `api.ts`/ActionBar adopt the typed envelope.
3. **00057 bim doc** — first non-note actions join the registry (`triage_list`, `triage_approve`) via the generic route; proves the checklist on a new action family.
4. **00055 bim CLI** — per-group Click modules; every group renders via `console.report_result`.

## Non-goals

- **CLI-only tools stay CLI-only**: fctracker, fren, morph, muc, netscan, outlookctl, pinger, puc, readerctl, sysup, vuc, zseq. No TUI/API/WebUI mandate for them.
- **dot stays CLI+TUI**; no dot API/WebUI.
- **pidash TUI is a read-only dashboard** (renders autopilot `state.json`); it is not an action surface and does not adopt the registry.
- **No Click generation from the registry**: Click commands stay hand-declared; the registry is not the CLI's source of truth (revisit only if CLI/registry drift actually bites).
- **Dual Rust/Python zettel domain stays as-is** (parity contract in `tests/lib/zettel/parity/`).
- **No new WebUI surfaces beyond bim serve**; WebUI auth remains the 00042 local-token model.

## Later (not required now)

- `dev/bin/scaffold.py` may emit an `actions.py` registry stub + envelope-mapped route for new multi-interface tools.

## Decisions log

- 2026-07-10, Bob: **commands are the seam**; registry mandatory only for name-based transports (rejected: forcing CLI/TUI through the registry — would rescope 00053/00054).
- 2026-07-10, Bob: **`success=False → HTTP 422`** with the envelope (rejected: 400 — conflates malformed requests FastAPI already 422s; 500 — wrong semantics).

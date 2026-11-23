# Port Plan: buvis/gems `src/tools/engram`

_Freshness: generated 2026-11-16 from buvis/engram `a0892e6` (master, PRD 00014 building; 00015 and 00016 in backlog) - regenerate if the source has moved on since. The port starts only after engram PRDs 00014, 00015 and 00016 are in engram's `prds/done/`; re-check this matrix against that commit before Phase 1._

Source: `~/git/src/github.com/buvis/engram` (`src/engram/`, `eval/`, `tests/`, `README.md`).
Target: `~/git/src/github.com/buvis/gems`, tool `src/tools/engram`, extra `engram`, script `engram`.
Decision: user, 2026-11-16 (ship engram inside buvis-gems instead of a local `uv tool install .`).

## QA handoff and source readiness (2026-11-23)

Standalone PRDs 00014-00016 are now in their source repository's
`docs/dev/project-management/prds/done/`. The source prerequisite is met;
the inventory still needs its required refresh against the selected port commit.
The subsequent Agoge findings belong to this Gems port, not another standalone
Engram batch. See [the QA handoff](00161-engram-qa-handoff.md) for all 11 held
source specifications, phase ownership, and compatibility conflicts.

Do not add standalone PRDs 00017-00027 as port prerequisites or copy them
unchanged into the Gems backlog. Their paths, configuration, CLI and test gates
describe the source. Adapt the accepted findings when creating target PRDs.
The parity contract below remains the baseline; record each deliberate bug-fix
exception and its consumer regression test before changing that contract.

## Contract that must not change

No consumer imports engram or reads its DB or config. Every consumer uses the
executable (portfolio search, 2026-11-16). The port keeps all of this
byte-identical:

1. Executable name `engram` on PATH.
2. Subcommands and flags: `query --scope --corpus -k/--k TEXT`; `index [--scope] [--corpus] [--rebuild] [--reembed-code] [--backfill-code]`; `lookup --name|--file [--scope] [--repo]`; `status [--scope]`; `harvest PATHS...`; `pack --cycle|--diff [--prd] [--capsule]`; `mcp`; `nudge {claude,codex,copilot,plain}`; `memory check [PATH]`; `memory migrate --from --to [--apply]`.
3. Stdout formats: tab-separated hit lines, `status` lines, `harvest` per-file lines, `lookup` lines, `memory` TSV, `pack` four stdout lines (absolute pack path first), `nudge` JSON per host.
4. Stderr text `not inside a registered repo` (autopilot `catchup.py`, `catchup_probe.py`, `review_stage.py` match it).
5. Exit codes, including `status` exit 1 for stale/dead rows and `nudge` always 0.
6. `docs/dev/tmp/engram-pack-{id}.md`, `review-diff-{id}.diff`, and the pack's `## Findings precedent` heading.
7. MCP tool name `engram_query` and its inputs.
8. Env vars `ENGRAM_NUDGE`, `ENGRAM_PACK_FILE`.
9. Data dir `~/.local/share/engram/` (DB `engram.db`, `eval/sources/`, `backups/`). The seatbelt profile `~/.config/seatbelt/ai-agents.sb:191-192` allows writes only there.

gems' `buvis_options` adds `--version/--config/--log-level/--debug/--update`.
Those are additive and allowed.

## Inventory Matrix

| row | classification | reason | code-only |
|-----|-----------------|--------|-----------|
| `query` (scope, corpus, -k, TSV output) | port | Core recall command; consumers parse its output. | no |
| `index` incremental (`--scope`, `--corpus`, default repo scope) | port | Catchup runs bare `engram index`. | no |
| `index --rebuild` (atomic swap, findings preserved, harvest/rebuild lock) | port | Documented recovery path for model mismatch. | no |
| `index --reembed-code` | port | Documented vector refresh. | no |
| `index --backfill-code` (engram PRD 00015) | port | Ships before the port; needed for module-context rollout. | no |
| `lookup --name/--file` | port | Documented exact symbol lookup. | no |
| `status` (per-corpus counts, stale/dead/in-flight, memory lines, exit codes) | port | Catchup and autopilot probe rely on output and exit code. | no |
| `harvest` (reviews and audit logs, per-file outcomes) | port | Catchup harvests review files. | no |
| `pack` (`--cycle/--diff/--prd/--capsule`, budgets, stdout, file names) | port | Autopilot review stage depends on it byte for byte. | no |
| `mcp` (`engram_query` stdio server) | port | agent-plugins engram plugin `mcp.json`. | no |
| `nudge <host>` with `ENGRAM_NUDGE` / `ENGRAM_PACK_FILE` | port | agent-plugins engram plugin hooks. | no |
| `memory check` | port | Documented repository-memory validator. | no |
| `memory migrate` | port | Documented migration command. | no |
| Corpora enumeration, gita registry discovery, memory attribution encoding, worktree resolution (engram PRD 00016) | port | Defines what gets indexed and which repo owns it. | no |
| Code chunking (exclusions, module context, None-heading migration) | port | Defines code corpus content; cache keys must match the existing DB. | no |
| Empty-code cache version migration (`_invalidate_legacy_empty_code`) | port | Runs on store open; must stay a no-op on the current DB. | yes |
| Embedding server lifecycle (spawn/stop llama-server, loopback endpoint check, leases, model identity) | port | Engram owns its llama-server instances. | no |
| Store at `~/.local/share/engram/engram.db`, model/dimension fail-loud | port | Same path and schema; no rebuild, pinned bge-m3 untouched. | no |
| Config file `~/.local/share/engram/config.toml` | redesign | Becomes gems `EngramSettings(GlobalSettings)` read from `~/.config/buvis/buvis-engram.yaml` (env prefix `BUVIS_ENGRAM_`): `embedding` list, `pinned_id`, `code.exclude_globs`, `transcripts.in_flight_seconds`, `data_dir` (default `~/.local/share/engram`). Endpoints and model ids go in the machine-local layer once gems PRD 00122 lands. | no |
| `[pack]` budget config (hard and per-section token caps) | redesign | Undocumented TOML section; moves into `EngramSettings.pack` with the same validation. | yes |
| Existing `config.toml` values | redesign | One-time: `engram` reads the old TOML only to print the equivalent YAML and exit 1 when `buvis-engram.yaml` is absent and `config.toml` exists. No silent dual config. | no |
| CLI layer (argparse in `cli.py`) | redesign | Rewritten in Click with `buvis_options`, lazy imports, `CommandResult`. Machine-read output must bypass rich formatting so item 3 of the contract stays byte-identical. | no |
| Harvest/rebuild write lock (`fcntl.flock`, engram PRD 00014) | redesign | gems builds Windows wheels; the lock needs a Windows path (`msvcrt.locking`) or a platform guard. | no |
| Python floor 3.12 and engram's lint profile | redesign | gems supports 3.11-3.15, mypy strict at 3.11, ruff with `ANN`/`S`/`PLR`; code is adjusted, behavior unchanged. | no |
| Main test suite (`tests/`, ~550 tests) | redesign | Moves to `tests/tools/engram/` with gems isolation fixtures; must pass on ubuntu/macOS x 3.11-3.15 and the 50% coverage gate. | no |
| Engram CI workflow (`.github/workflows/test.yml`) | redesign | Replaced by gems' per-tool CI matrix. | no |
| Installation (`uv tool install .`) | redesign | Becomes `uv tool install 'buvis-gems[engram]'`; sysup's `uv tool upgrade --all` keeps it current. | no |
| README documentation | redesign | Becomes gems tool docs; private-eval and harness sections dropped. | no |
| `eval/` research tooling (comparisons, probes, agent-session miner/judge, results, gold labels) | drop | Research only, needs private data and local GGUFs; stays in the archived engram repo. | no |
| Model harness and pin writer (`src/engram/harness.py`, `eval/harness.py`) | redesign | Becomes per-machine `engram bench` (see "Per-machine model selection"): quality comes from a committed table, hardware fit is measured on each machine, the pick goes to that machine's local config. The gold-set scoring itself stays in the archive. | no |
| `private` marker and gold-source validation test | drop | Validates dropped eval data; data stays on disk. | no |

Classification legend:

- **port** - ports unchanged.
- **redesign** - ports with modification; the `reason` column explains what changes and why.
- **drop** - does not port; the `reason` column explains why it stays behind.

`code-only` marks a row discovered only in code, absent from docs/SKILL.md/README, and therefore not yet judged by anyone.

## Drop Rulings

### `eval/` research tooling

- **Evidence presented**: ~25 modules plus result JSONs, `goldset.yaml`, `passage_labels.yaml`, 47+ eval tests. It produced the 2026-11-13 adoption evidence (36/44 judged relevant). Intakes 00008/00009 would need it again. It needs private data and local GGUF models and is not user-facing. Options shown: drop to archive, port as dev tooling, keep engram repo as eval-only.
- **Ruling**: drop; stays in the archived engram repo (user, 2026-11-16). Accepted cost: a future reranker or fusion experiment must revive it against gems imports.

### Model harness and pin writer

- **Evidence presented**: `src/engram/harness.py` and `eval/harness.py` score models and write `[pinned] id` into `config.toml`. Production is pinned to bge-m3 with no repin planned. Options shown: drop with eval, port writing YAML.
- **Ruling**: drop with eval (user, 2026-11-16). **Superseded the same day**: the user requires benchmarking and selecting models per machine, because machines differ in hardware. The row is now `redesign`; see "Per-machine model selection".

### `private` marker and gold-source validation test

- **Evidence presented**: `~/.local/share/engram/eval/sources/` holds 53 retained transcripts, 21 with no other copy, pinned by `eval/sources.json`. One `private` test validates it. Options shown: drop test and keep data, port the test.
- **Ruling**: drop the test, keep the data on disk untouched (user, 2026-11-16). Nothing deletes `~/.local/share/engram/eval/`.

## Per-machine model selection

Requirement (user, 2026-11-16): benchmark and select the embedding model per
machine, because machines differ in hardware. Retrieval quality does not
depend on hardware; speed and memory fit do. So the work splits in three:

1. **Quality, measured once.** A committed table in gems,
   `src/tools/engram/model_quality.toml`: model id, quality score, metric name,
   source (archived eval run and date). Seed it from the archived eval results
   for the candidates in engram's `eval/models.toml` (bge-m3, Qwen3-Embedding
   0.6B/4B/8B, embeddinggemma-2, jina-v5-small, F2LLM-v2 4B/8B/14B). A model
   without a row is "unscored" and is never picked automatically. Refreshing
   quality stays a job for the archived eval on the machine that holds the
   private gold sources; its output is a table edit in gems.
2. **Fit, measured on each machine.** `engram bench [--models ID...]` runs on
   any machine with no private data. For each candidate it starts llama-server
   with the same flags engram uses, records whether the model loads, peak
   resident memory, and embedding throughput and p95 latency on a fixed
   synthetic corpus bundled in gems. It prints one TSV line per model and
   writes nothing.
3. **Select per machine.** `engram bench --apply` picks the highest-quality
   scored model that loaded and meets the machine's budgets
   (`bench.min_chunks_per_second`, `bench.max_rss_mb` in `EngramSettings`). It
   writes `pinned_id` and the embedding entry to that machine's local config
   layer `~/.local/.config/buvis/buvis-engram.yaml` (gems PRD 00122), never to
   the shared `~/.config/buvis` file. Each machine has its own DB, so a changed
   pick still hits the existing model-mismatch fail-loud: `--apply` prints that
   `engram index --rebuild` is required and never runs it.

The production pin (bge-m3 on this machine) does not change unless the user
runs `--apply` there.

## Consumer Cutover

The contract section keeps every reference valid, so most consumers need no edit.

| consumer | current reference | new reference | cutover step |
|----------|--------------------|----------------|---------------|
| Install (`~/.local/bin/engram` -> `~/.local/share/uv/tools/engram`) | `uv tool install .` from the engram checkout | `uv tool install 'buvis-gems[engram]'` | Phase 4 hand-off: `uv tool uninstall engram`, then install or upgrade buvis-gems with the extra. Both cannot own `~/.local/bin/engram`. |
| agent-plugins `plugins/engram/` (`mcp.json`, `hooks.json` x3, pi `engram-nudge.ts`, skill, README, tests) | bare `engram mcp`, `engram nudge <host>`, `engram query/status` | unchanged | README install line points at `buvis-gems[engram]` (Phase 4). |
| agent-plugins `plugins/autopilot/scripts/catchup.py:40-49`, review-work-completion skill and agent registry | `engram status --scope repo`, stderr text, `engram-pack-{id}.md` | unchanged | Contract test in Phase 3 covers it; no edit. |
| claude-autopilot `review_stage.py`, `catchup_probe.py` (FROZEN repo; installed autopilot 0.10.0) | `engram pack --cycle/--prd/--capsule`, stdout path, `## Findings precedent`, stderr text | unchanged | None allowed (frozen). Phase 3 contract tests replay its exact calls. |
| claude-git-ferry `skills/catchup/SKILL.md:42-65` | `engram harvest/index/query/status` | unchanged | None. |
| agent-skills `skills/catchup/SKILL.md` and `docs/plugin-skills/review-work-completion/SKILL.md:173-182` | bare `engram`; fallback `uv run --project <your engram checkout> engram pack` | fallback names `buvis-gems[engram]` | Phase 4: edit the fallback sentence in agent-skills. |
| home `~/.config/seatbelt/ai-agents.sb:191-192` | write allow `~/.local/share/engram` | unchanged | None (data dir kept). |
| home `~/.claude/warden.yaml:42` | `engram` allowlisted | unchanged | None. |
| sysup `default.yaml:49` | `uv tool upgrade --all` (cannot refresh a directory install) | same step now upgrades buvis-gems with the extra | None; verify after Phase 4. |

## Phases (dependency order)

1. **Core library port** - no dependencies. Precondition: engram PRDs 00014-00016 done; record the source commit. Scaffold `src/tools/engram` with `tools/lib/scaffold.py` (extra `engram`: `sqlite-vec`, `tree-sitter-language-pack`; mypy `ignore_missing_imports` for both). Port every non-CLI module except `harness.py`, adapted to Python 3.11, mypy strict and the ruff profile, with the Windows-safe write lock. Port the main tests (minus the `private` test) to `tests/tools/engram/`. Exit: gems CI green on all matrix cells; wheels for the extra resolve on Windows.
2. **Settings** - depends on Phase 1 landing and its exit criteria holding. `EngramSettings(GlobalSettings)` with `embedding`, `pinned_id`, `code`, `transcripts`, `pack`, `data_dir`; the library reads settings instead of `config.toml`; the old-TOML detection prints the YAML equivalent and exits 1. Exit: settings tests pass; a YAML equal to today's `config.toml` gives identical `EngramConfig` values.
3. **Click CLI with contract tests** - depends on Phase 2 landing and its exit criteria holding. All 13 commands in Click; contract tests replay every consumer call in the Consumer Cutover table against a temp store and compare stdout, stderr and exit codes to golden output captured from the standalone engram at the Phase 1 source commit. Exit: contract tests pass; `engram --help` lists every subcommand.
4. **Release and cutover** - depends on Phase 3 landing and its exit criteria holding. Release gems with the extra; user hand-off to swap the install; write `buvis-engram.yaml` from the current `config.toml`; verify `engram status --scope portfolio`, one `engram pack --cycle` in a registered repo, and `engram mcp` initialize; update the agent-skills fallback sentence and the agent-plugins engram README. Exit: installed `engram` comes from buvis-gems; the production DB is unchanged (same SHA-256 before and after a read-only status run); no rebuild ran.
5. **Per-machine benchmark and selection** - depends on Phase 4 landing and its exit criteria holding, and on gems PRD 00122 (machine-local config layer) being done. `model_quality.toml` seeded from the archived results, bundled synthetic bench corpus, `engram bench` and `bench --apply` per the section above. Exit: bench tests pass with a fake server; `bench --apply` writes only the machine-local file; a real `engram bench` on this machine reports bge-m3 as loaded.
6. **Retire the standalone repo** - depends on Phase 5 landing and its exit criteria holding. Retirement PRD in buvis/engram (below).

Do not start a phase until the phase before it has landed and its exit criteria hold.

## Retirement

The retirement PRD belongs to buvis/engram (the repo where the code dies), and is written alongside the final port phase rather than remembered later.

Retire `~/git/src/github.com/buvis/engram` (product code `src/engram/`, `tests/`, CI) once every criterion below holds. Archive, do not delete: `eval/` and the PRD/review history stay readable there.

| row | classification | reason | code-only |
|-----|-----------------|--------|-----------|
| `query` | port | Core recall command; consumers parse its output. | no |
| `index` incremental | port | Catchup runs bare `engram index`. | no |
| `index --rebuild` | port | Documented recovery path. | no |
| `index --reembed-code` | port | Documented vector refresh. | no |
| `index --backfill-code` | port | Module-context rollout. | no |
| `lookup` | port | Exact symbol lookup. | no |
| `status` | port | Catchup and probe rely on it. | no |
| `harvest` | port | Catchup harvests reviews. | no |
| `pack` | port | Autopilot review stage. | no |
| `mcp` | port | engram plugin MCP server. | no |
| `nudge` | port | engram plugin hooks. | no |
| `memory check` | port | Repository-memory validator. | no |
| `memory migrate` | port | Memory migration. | no |
| Corpora, registry, attribution, worktrees | port | What gets indexed and who owns it. | no |
| Code chunking | port | Code corpus content and cache keys. | no |
| Empty-code cache migration | port | Store-open migration. | yes |
| Embedding server lifecycle | port | Engram-owned llama-server. | no |
| Store and model fail-loud | port | Same DB, no rebuild. | no |
| Config file | redesign | `buvis-engram.yaml` via `EngramSettings`. | no |
| `[pack]` budget config | redesign | Into `EngramSettings.pack`. | yes |
| Existing `config.toml` values | redesign | Detect, print YAML, exit 1. | no |
| CLI layer | redesign | Click, byte-identical machine output. | no |
| Write lock | redesign | Windows-safe. | no |
| Python floor and lint | redesign | 3.11, mypy strict, ruff. | no |
| Main test suite | redesign | `tests/tools/engram/`. | no |
| CI workflow | redesign | gems CI. | no |
| Installation | redesign | `buvis-gems[engram]`. | no |
| README | redesign | gems tool docs. | no |
| `eval/` tooling | drop | Stays in archive. | no |
| Model harness | redesign | Per-machine `engram bench` with committed quality table. | no |
| `private` test | drop | Stays in archive; data kept on disk. | no |

- [ ] Every row above is classified, and every row with `code-only` = no has its test/doc/config follow-up landed.
- [ ] `query` ports cleanly: contract test replays `engram query --scope repo "<q>" -k 5` and `--scope portfolio --corpus findings` with byte-identical TSV.
- [ ] `index` incremental ports cleanly: bare `engram index` in a registered repo indexes repo scope; unchanged content embeds nothing.
- [ ] `index --rebuild` ports cleanly: rebuild on a temp store swaps atomically, keeps findings, refuses while harvest holds the lock.
- [ ] `index --reembed-code` ports cleanly: prints `re-embedded N code chunks` and replaces only vectors.
- [ ] `index --backfill-code` ports cleanly: engram PRD 00015's tests pass in gems.
- [ ] `lookup` ports cleanly: `--name` and `--file` output and exit 1 on no match match the standalone.
- [ ] `status` ports cleanly: `status --scope repo` outside a registered repo prints `not inside a registered repo` on stderr; stale/dead exits 1.
- [ ] `harvest` ports cleanly: per-file `path<TAB>outcome<TAB>count` lines and exit codes match.
- [ ] `pack` ports cleanly: autopilot's exact `pack --cycle ID --prd ABS --capsule ...` call prints the absolute pack path first and writes `docs/dev/tmp/engram-pack-ID.md` with `## Findings precedent`.
- [ ] `mcp` ports cleanly: `initialize`, `tools/list` (`engram_query`), `tools/call` match the standalone.
- [ ] `nudge` ports cleanly: all four hosts emit identical JSON/text; `ENGRAM_NUDGE=off` and `ENGRAM_PACK_FILE` behave the same; exit is always 0.
- [ ] `memory check` ports cleanly: violation TSV and exit codes match.
- [ ] `memory migrate` ports cleanly: dry-run TSV, `--apply` writes and rollback match.
- [ ] Corpora, registry, attribution and worktree resolution port cleanly: engram's corpora, memory-attribution and worktree tests pass in gems.
- [ ] Code chunking ports cleanly: chunks for the engram test fixtures equal the standalone's, so unchanged files are not re-chunked on the production DB.
- [ ] Empty-code cache migration ports cleanly: opening the production DB leaves `empty_sources` unchanged.
- [ ] Embedding server lifecycle ports cleanly: spawn, reuse and stop tests pass; non-loopback endpoints are rejected.
- [ ] Store ports cleanly: the production DB opens without a model-mismatch error and without a rebuild.
- [ ] Every consumer listed in the Consumer Cutover table now points at `new reference`, and no code still references `current reference`.
- [ ] CI is green on the branch that removes `~/git/src/github.com/buvis/engram` product code.
- [ ] `~/.local/bin/engram` resolves into the buvis-gems uv tool, and `uv tool list` no longer shows a standalone `engram`.
- [ ] `~/.local/share/engram/` (DB, `eval/sources/`, `backups/`) is untouched: same file list and DB SHA-256 as before Phase 4.
- [ ] `engram bench` runs on this machine without private data, and `engram bench --apply` writes only `~/.local/.config/buvis/buvis-engram.yaml`.
- [ ] The engram repo README says it is archived and points at buvis-gems; archiving the GitHub repo is a user hand-off (irreversible-ish, needs explicit approval).

Hand this Retirement block to `create-prd` to lift verbatim into the retirement PRD alongside the final port phase, not later. The criteria above are what that PRD is checked against when it executes; they are not a precondition for writing it.

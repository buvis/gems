# pidash — PRD Dashboard TUI

Read-only Textual TUI that displays autopilot PRD cycle progress. Watches `.local/prd-cycle.json` for changes and updates the display in real time.

## Decisions

- **Technology:** Python + Textual. Cross-platform (macOS, Windows). Ships as part of buvis-gems.
- **Layout:** Single-PRD focus (layout C). Pipeline breadcrumb at top, progress bar, three detail panels below. No kanban grid.
- **Data refresh:** File watcher via `watchfiles`. Instant updates on write, zero CPU otherwise.
- **Empty state:** Shows dimmed pipeline with "no active cycle" message. Watches for `prd-cycle.json` to appear.
- **Interactivity:** None. Read-only display. `q` quits, `r` manual refresh.

## Data Model

Source: `.local/prd-cycle.json` (written by autopilot at every phase transition).

```python
class Decision(BaseModel):
    description: str
    severity: str  # low, medium, high, critical
    resolution: str  # auto description or "pending"

class CycleResult(BaseModel):
    cycle: int
    critical: int = 0
    high: int = 0
    low: int = 0

class PrdInfo(BaseModel):
    name: str
    path: str = ""
    filename: str = ""

class PrdState(BaseModel):
    prd: PrdInfo
    phase: str  # catchup | planning | work | review | decision-gate | rework | paused | done
    phases_completed: list[str] = []
    cycle: int = 0
    tasks_completed: int = 0
    tasks_total: int = 0
    autonomous_decisions: list[Decision] = []
    deferred_decisions: list[Decision] = []
    review_cycles: list[CycleResult] = []
    done_prds: list[str] = []
```

Phase-to-display mapping:
- `catchup` → CATCHUP
- `planning` → PLANNING
- `work`, `rework` → WORKING
- `review`, `decision-gate`, `paused` → REVIEWING
- `done` → DONE

## UI Components

```
PidashApp (App)
  ├─ HeaderBar (Static) — PRD name, cycle number, last-updated timestamp
  ├─ PhasePipeline (Horizontal) — 5 phase labels: ✓ completed, ▸ active, dimmed future
  ├─ ProgressBar (Static) — task count + filled bar (visible during WORKING only)
  ├─ Horizontal (Container)
  │   ├─ TaskPanel (Static, scrollable) — ✓ done, ▸ in-progress, ○ pending
  │   ├─ DecisionPanel (Static, scrollable) — auto decisions dimmed, pending in red with ⚠
  │   └─ CyclePanel (Static, scrollable) — per-cycle severity breakdown
  └─ FooterBar (Static) — keybindings: q quit, r refresh
```

All widgets are read-only `Static`. On state change, re-parse JSON and call `update()` on each widget.

## File Structure

```
src/tools/pidash/
├── __init__.py
├── manifest.toml          # tool metadata
├── commands/
│   └── __init__.py        # Click CLI: pidash [project-path]
└── tui/
    ├── __init__.py
    ├── app.py             # PidashApp
    ├── widgets.py         # all widget classes
    ├── state.py           # Pydantic models
    └── watcher.py         # watchfiles worker
```

Integration:
- Entry point in `pyproject.toml`: `pidash = "buvis.tools.pidash.commands:cli"`
- Optional deps: `pidash = ["textual>=3,<4", "watchfiles>=1.0"]`
- Declared separately from bim — no cross-dependency

## File Watcher

Runs as a Textual `Worker`:
1. On startup, check if `.local/prd-cycle.json` exists
2. If not, watch `.local/` (or project root) for creation
3. Once file exists, watch for modifications
4. On each change, parse JSON → post message to app → widgets update

## Error Handling

- **Malformed JSON (mid-write):** Skip update, keep displaying last valid state
- **Missing fields:** Pydantic defaults fill gaps. Minimal valid state: `prd.name` + `phase`
- **File deleted:** Revert to empty "waiting" state, keep watching for re-creation
- **Permission errors:** Show one-line error in header, keep watching
- **No `.local/` directory:** Show empty state, watch for directory to appear
- **Rapid writes:** `watchfiles` debounces (50ms), Textual event loop handles the rest

## Testing

In `tests/pidash/`:

- **`test_state.py`** — Pydantic parsing: valid JSON, minimal JSON, malformed returns None, defaults applied, phase mapping
- **`test_widgets.py`** — Each widget renders given a PrdState: pipeline highlights, progress bar math, task icons (✓/▸/○), decision separation, cycle severity formatting
- **`test_app.py`** — Textual async pilot: starts empty, state update re-renders, file deletion reverts to empty

No integration tests for file watcher — `watchfiles` and Textual workers are framework code.

## CLI

```
pidash [PROJECT_PATH]
```

- `PROJECT_PATH`: path to project directory (default: current working directory)
- Looks for `.local/prd-cycle.json` relative to that path
- Exits with `q` key

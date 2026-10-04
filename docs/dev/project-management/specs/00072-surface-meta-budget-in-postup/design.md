# Surface the meta-budget share in postup

<!-- design; migrated from PRD 00072 flat file -->

## Structural Decomposition

### Repository Structure

```
src/tools/postup/
├── domain/meta_share.py         # Maps to: Compute meta share (postup layout per 00063)
├── adapters/web/frontend/src/   # Maps to: Render with ceiling state (web tile, 00065 app)
└── commands/brief/              # Maps to: Render with ceiling state (text tile, 00068 renderer)
```

### Module: postup.domain.meta_share
- **Maps to capability**: Meta-share metric
- **Responsibility**: ledger parse + attribution + percentage; pure, UI-free
- **Exports**: `collect(window_days=30) -> MetaShare`

### Module: brief tiles (00065 web frontend + 00068 text brief)
- **Maps to capability**: Meta-share metric
- **Responsibility**: render the tile in the existing web and text brief surfaces; no new top-level directories
- **Exports**: view fragment consuming `MetaShare`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **postup.domain.meta_share**: pure read of the cost ledger

### Core Layer (Phase 1)
- **brief tiles**: Depends on [postup.domain.meta_share, postup web core (gems
  PRD 00065) and text brief (00068) existing]

### Integration Layer (Phase 2)
- none (two-phase PRD; heading retained per template)

## Test Strategy

### Critical Scenarios
- **Happy path**: fixture ledger with 25% meta → Expected: green tile "25%".
- **Edge case**: 30.0% exactly → Expected: red (ceiling is inclusive).
- **Error case**: costs.jsonl missing → Expected: "meta n/a", no crash.

## Risks

- **Attribution drift** (ledger schema changes): collector premise re-check +
  unknown-counts-as-product keeps the metric conservative.
- **Sequencing**: depends on postup 00065/00068 landing first; if the postup
  chain stalls, this PRD stays parked behind it by its declared dependency.

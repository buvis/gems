# fctracker: validate CSV order and handle bad/overdraft rows

<!-- design; migrated from PRD 00048 flat file -->

## Implementation

### Module: fctracker (reader + command layer)
- **Location**: `src/tools/fctracker/adapters/transactions/transactions_reader.py`, `src/tools/fctracker/commands/transactions/transactions.py`
- **Responsibility**: reject wrong-ordered / malformed input loudly; translate domain errors into `CommandResult`.
- **Exports**: reader gains an order assertion; command handler catches the three error classes.

### Dependencies
- No dependencies.

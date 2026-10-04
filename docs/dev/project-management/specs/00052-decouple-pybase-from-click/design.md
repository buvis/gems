# Decouple pybase from Click at import time

<!-- design; migrated from PRD 00052 flat file -->

## Implementation

### Module: pybase.configuration + pybase.updater
- **Location**: `src/lib/buvis/pybase/configuration/click_integration.py`, `configuration/__init__.py`, `src/lib/buvis/pybase/updater/*`
- **Responsibility**: settings + option plumbing that does not force Click on non-CLI consumers; updater output through the console.
- **Exports**: `buvis_options` (installs the patch on first use), `GlobalSettings` (import-side-effect-free), updater functions (console output)

### Dependencies
- Independent of the seam spec (sequenced in P2 because it unblocks headless lib consumers). No dependency on a higher-numbered PRD.

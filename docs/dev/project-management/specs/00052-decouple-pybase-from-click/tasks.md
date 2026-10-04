# Decouple pybase from Click at import time

<!-- tasks; migrated from PRD 00052 flat file -->

## Tasks

### Phase 0: Core
- [ ] Move the `_install_parse_args_patch()` call from module level into `buvis_options` (idempotent install) — Acceptance: importing `configuration` does not alter `click.Command.parse_args`; all tools' CLIs still intercept `--update`.
- [ ] Route updater `click.echo` output through the console adapter — Acceptance: updater messages carry console prefixes; no `click.echo` remains in `updater/`.
- [ ] Stop re-exporting Click glue from `configuration/__init__` (or make it lazy) — Acceptance: the import-side-effect-free regression test passes; `mypy`/`pytest` green.

# backup gem: Phase-2 CLI + perf enhancements v1

<!-- tasks; migrated from PRD 00083 flat file -->

## Tasks

### Phase 0: overrides + introspection
- [ ] `--source`/`--out` overrides with precedence + multi-instance guard —
      Acceptance: override backs up a temp tree without touching config; two
      instances + `--source` errors via `console`.
- [ ] `--show-excludes <instance> --for <path>` — Acceptance: resolved set matches
      what a real run of that instance archives under that path.

### Phase 1: perf engine
- [ ] `engine: system-tar` opt-in `tar -T` path with Python-owned selection —
      Acceptance: member set byte-equivalent to the Python engine on a fixture;
      BSD + GNU `tar` both handled or fall back with a warning.

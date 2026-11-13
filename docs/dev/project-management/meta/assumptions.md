# Assumptions ledger: 00136-sysup-plan-config-errors-raw-v1

## 1: sysup: project merged config onto plan keys, reject list directives and render plan errors cleanly

- Tess: messages must contain the full `buvis-sysup.yaml` path, not the basename; `COLUMNS=500` keeps Rich from wrapping it.
- Tess: "single line" means exactly one non-empty CLI output line.
- Tess: the bundled plan still has a `brew` command (shared with `test_config.py`).
- Ivan (qwen): `merge_configs(merged, data)` raises `ConfigurationError` for a list directive on a mapping key.
- Ivan (qwen): `SysupSettings.model_fields` exposes `debug`/`log_level` with no aliases.
- Ivan (MEDIUM fix): per-entry source tracking applies to every mapping plan key (`commands`, `expiry`, `ntfy`); entry names are stringified to match `loc`.
- Orchestrator (all tasks): per-task review ran as a native Agent at sonnet because `sonnet-run.sh` failed auth (`CLAUDE_CODE_OAUTH_TOKEN` unset in this session).

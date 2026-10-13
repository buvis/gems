---
default_model: opus
model_tier_rationale: invented classification and gating predicates, a secret-handling path (stdin only), an optional-dependency seam, and config contracts the bundled template and user config depend on; final text is given for the pure parts, the subprocess and TTY orchestration is designed here
---

# sysup expiry registry: tracked credentials, gh and X.509 checks, `needs:` gating, guided `sysup refresh`

Source: `docs/dev/project-management/intake/processed/00092-sysup-expiry-tracking/discovery.md` (PRD B of two; depends on PRD 00092, the attention layer)

## Overview

### Problem Statement
Credentials with a hard expiry are tracked nowhere. The agent's gh token in `~/.config/gh-agent` reports its expiry in the `Github-Authentication-Token-Expiration` header of `gh api -i user` (measured 2026-10-13: `2027-10-13 18:05:04 UTC`), and the first signal of its death will be a failing `gh` call inside a Seatbelt session that cannot fix it: no Keychain, and the refresh needs a browser.
On 2026-10-12 a token that authenticated fine still could not read a private repository because its repository access had stayed "Public repositories (read-only)", so an expiry date alone is not enough: the grant has to be probed too.
sysup is the recurring maintenance run and, after PRD 00092, every not-ok outcome it reports is summarised, persisted, pushed and reflected in the exit code. This PRD adds expiring items as one more kind of check feeding that record, lets a command declare that it needs an item, and gives the human a guided, terminal-only refresh procedure whose pasted secret never touches argv, env, logs, state or a notification.

### Target Users
The solo operator whose agent sessions depend on `~/.config/gh-agent`, and any host that tracks a certificate file or a TLS endpoint through local sysup config.

### Success Metrics
- `uv run pytest tests/tools/sysup/test_gh_token.py -q` passes: `test_header_date_maps_to_ok_expiring_expired_around_warn_days`, `test_probe_denied_reports_unknown_grant_broken`, `test_missing_gh_reports_unknown`, `test_config_dir_is_passed_as_env_not_argv`, `test_missing_header_reports_unknown`.
- `uv run pytest tests/tools/sysup/test_x509.py -q` passes with cryptography installed: `test_pem_file_not_after`, `test_host_port_uses_get_server_certificate`, `test_missing_extra_reports_unknown_with_install_hint`, `test_exactly_one_of_path_or_host`; `uv run pytest tests/tools/sysup/test_x509.py -q -rs` reports the first two as skipped when cryptography is absent (the import-skip guard).
- `uv run pytest tests/tools/sysup/test_refresh.py -q` passes: `test_secret_goes_only_to_stdin_of_the_declaring_command`, `test_no_secret_prompt_without_stdin_secret`, `test_failed_command_stops_and_reports_exit_code`, `test_env_values_are_tilde_expanded`.
- `uv run pytest tests/tools/sysup/test_runner.py -q` passes: `test_items_are_checked_before_prime_and_commands`, `test_dry_run_skips_item_probes`, `test_needs_expired_item_skips_command_with_refresh_hint`, `test_needs_unknown_item_skips_command`, `test_needs_ok_or_expiring_item_runs_command`, `test_capability_exception_becomes_unknown`.
- `uv run pytest tests/tools/sysup/test_sysup_cli.py -q` passes: `test_refresh_refuses_without_tty`, `test_refresh_runs_procedure_then_rechecks_and_clears_on_ok`, `test_refresh_recheck_not_ok_keeps_entry_and_exits_1`, `test_refresh_disabled_item_is_refused`, `test_filtered_run_still_checks_every_item`, `test_summary_adds_refresh_hint_for_items`.
- `uv run pytest tests/tools/sysup/test_config.py tests/tools/sysup/test_default_config.py -q` passes: `test_expiry_item_validates_with_defaults`, `test_enabled_gh_item_without_probe_is_rejected`, `test_disabled_template_without_probe_loads`, `test_unknown_expiry_capability_rejected`, `test_needs_unknown_item_rejected`, `test_item_and_command_name_collision_rejected`, `test_gh_agent_template_is_disabled_and_has_no_probe`.
- `uv run python -c "import tomllib; d = tomllib.load(open('pyproject.toml','rb'))['project']['optional-dependencies']; assert d['sysup-cert'] == ['cryptography>=42,<51'] and 'sysup-cert' in d['all'][0]"` exits 0.

## Functional Decomposition

### Capability: Expiry registry in config
Items are declared beside commands and layer the same way.

#### Feature: `expiry:` map and its models
- **Description**: `SysupConfig` gains `expiry: dict[str, ExpiryItem]`; each item names a code-owned expiry capability, its inputs, a warning threshold, an optional refresh procedure, and the same `enabled` / `when` envelope as a command.
- **Inputs**: the merged layers `load_config` already builds (`src/tools/sysup/config.py:119-157`): bundled `default.yaml`, `buvis-sysup.yaml`, its `.local.yaml` twin, `--config`.
- **Outputs**: frozen, `extra="forbid"` models beside `SysupCommand` (`src/tools/sysup/config.py:39-61`):

```python
class RefreshCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    argv: tuple[str, ...]
    env: dict[str, str] = {}
    stdin: Literal["secret"] | None = None


class RefreshSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    instructions: str
    commands: tuple[RefreshCommand, ...] = ()


class ExpiryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    use: str
    with_: dict[str, object] = Field(default_factory=dict, alias="with")
    warn_days: int = 30
    refresh: RefreshSpec | None = None
    enabled: bool = True
    when: WhenSpec = WhenSpec()
```

- **Behavior**: `SysupCommand` gains `needs: tuple[str, ...] = ()`. A command's `with_` alias handling is reused verbatim. An empty `argv` is a validation error (`min_length=1` on the tuple).

#### Feature: Validation in `load_config`
- **Description**: `_validate_expiry(cfg)` runs after `_validate_capabilities` (`src/tools/sysup/config.py:73-100`) and raises `FatalError` with one clear message per rule.
- **Inputs**: the validated `SysupConfig`.
- **Outputs**: nothing, or `FatalError`.
- **Behavior**: rules and exact messages: unknown capability `item '<name>': unknown expiry capability '<use>'`; unknown input `item '<name>': capability '<use>' got unknown input(s) <keys>; accepted: <keys>` (same shape as the command rule); required input missing on an enabled item `item '<name>': capability '<use>' requires input '<key>' before it can be enabled` where a required input is one whose default in the capability's `inputs` mapping is `None` and whose `with:` value is absent, `None` or an empty string (disabled items skip this rule, which is what lets the bundled template ship without a probe); name collision `'<name>' is both a command and an expiry item`; dangling reference `command '<name>': needs unknown expiry item '<item>'`. Decided 2026-10-13 at create-prd: the required-input rule applies to expiry items only; command capabilities keep today's behaviour (none of them has a `None` default, `src/tools/sysup/capabilities/nvim_mason.py:65-67` and siblings).

#### Feature: Applicable items
- **Description**: `applicable_items(cfg)` returns the enabled items whose `when` matches this host, sorted by name.
- **Inputs**: the `expiry` map of the config.
- **Outputs**: `list[tuple[str, ExpiryItem]]`.
- **Behavior**: the three checks of `applicable_commands` (`src/tools/sysup/config.py:160-179`) move into one helper `_applies(entry)` (enabled, `when.os` equals `sys.platform`, `when.check` resolves) that both functions call; `applicable_commands` keeps its `(order, name)` sort and its return shape.

#### Feature: Bundled `gh-agent` template
- **Description**: `default.yaml` ships a disabled `gh-agent` item with the refresh steps from the idea; the user supplies a private-repository probe and `enabled: true` in `buvis-sysup.local.yaml`.
- **Inputs**: none at runtime.
- **Outputs**: the item below, appended to `src/tools/sysup/default.yaml` after the `prime` block (`src/tools/sysup/default.yaml:86-89`):

```yaml
# Expiring credentials checked before every ordinary run (PRD 00096). gh-agent
# is a disabled template: in buvis-sysup.local.yaml set `with.probe` to a
# `gh api` path that needs private-repository access (for example
# repos/<owner>/<private-repo>) and `enabled: true`. The other fields merge in.
expiry:
  gh-agent:
    enabled: false
    use: gh-token-expiry
    with:
      config_dir: ~/.config/gh-agent
    warn_days: 30
    refresh:
      instructions: |
        1. Open https://github.com/settings/personal-access-tokens/new
        2. Token name: gh-agent. Resource owner: buvis. Expiration: 1 year.
        3. Repository access: All repositories.
        4. Permissions: Pull requests (read and write), Issues (read and write),
           Actions (read), Commit statuses (read), Contents (read), Metadata (read).
        5. Generate the token, copy it, and paste it at the prompt below.
      commands:
        - argv: [gh, auth, login, --with-token, --insecure-storage]
          env: { GH_CONFIG_DIR: ~/.config/gh-agent }
          stdin: secret
```

- **Behavior**: `_load_default` reads the bundled file with plain `yaml.safe_load` (`src/tools/sysup/config.py:103-116`), so no `${HOME}` substitution is available there; the capability and the refresh runner expand `~` themselves. No personal probe target is bundled.

### Capability: Expiry capabilities
Code-owned probes that return when something expires, or why that is unknown.

#### Feature: `ExpiryCapability` protocol and registry
- **Description**: A second protocol and registry in `src/tools/sysup/capabilities/__init__.py` beside `Capability` and `CAPABILITIES` (`src/tools/sysup/capabilities/__init__.py:19-43`).
- **Inputs**: `inputs` (accepted `with:` keys mapped to defaults, `None` marking a required key) and `expires_at(**kwargs)`.
- **Outputs**: `expires_at` returns an aware `datetime`, or a `str` naming why the expiry is unknown.
- **Behavior**: `EXPIRY_CAPABILITIES = {"gh-token-expiry": GhTokenExpiry(), "x509-expiry": X509Expiry()}`. Decided 2026-10-13 at create-prd: a string return rather than an exception class for the unknown case (no custom exception for control flow); any exception that still escapes is caught by the runner and reported as unknown with its text, except `FatalError`, which propagates as it does for commands.

#### Feature: `gh-token-expiry`
- **Description**: Reads the expiration header under the item's `GH_CONFIG_DIR`, then probes the grant with one authenticated call that needs private-repository access.
- **Inputs**: `config_dir` (required) and `probe` (required, a `gh api` path such as `repos/<owner>/<private-repo>`).
- **Outputs**: the parsed header datetime, or one of: `gh not found`; `gh api user failed: <stderr>`; `no Github-Authentication-Token-Expiration header (token without expiry?)`; `unparseable expiration header: <value>`; `grant broken: gh api <probe>: <stderr>`.
- **Behavior**: `src/tools/sysup/capabilities/gh_token.py`: `shutil.which("gh")` immediately before use; `subprocess.run([gh, "api", "-i", "user"], env={**os.environ, "GH_CONFIG_DIR": str(Path(config_dir).expanduser())}, capture_output=True, text=True, check=False, timeout=30)`; the header is found case-insensitively at a line start with `re.compile(r"(?im)^github-authentication-token-expiration:\s*(.+?)\s*$")`; `parse_expiration(value)` returns `datetime.strptime(value.replace(" UTC", " +0000"), "%Y-%m-%d %H:%M:%S %z")` (the measured format, with a numeric offset also accepted); the probe is `subprocess.run([gh, "api", "--silent", probe], ...)` with the same env, and any non-zero exit is `grant broken`, which covers the 2026-10-12 failure mode and, by accepted decision (Q6), a network blip. `GH_CONFIG_DIR` goes in the environment of the child only, never in argv.

#### Feature: `x509-expiry`
- **Description**: Reads the not-after date of a PEM file or of the certificate a TLS endpoint presents.
- **Inputs**: exactly one of `path` (PEM file) or `host` (`name` or `name:port`, port 443 by default); both default to `""`, neither is required by the config rule.
- **Outputs**: `cryptography.x509.Certificate.not_valid_after_utc`, or one of: `x509-expiry needs exactly one of path or host`; `x509-expiry needs the sysup-cert extra: uv tool install 'buvis-gems[sysup-cert]'`; `<ExceptionName>: <text>` for an unreadable file, a bad PEM, a refused or timed-out connection.
- **Behavior**: `src/tools/sysup/capabilities/x509.py` imports `cryptography.x509` inside `expires_at` (a core-only install must import sysup and run gh tracking without the extra); a file is `Path(path).expanduser().read_bytes()`; a host is fetched with the stdlib ssl module's `get_server_certificate((name, port), timeout=10)`, whose PEM string is encoded to bytes; both go through `cryptography.x509.load_pem_x509_certificate`. `OSError` (which covers the ssl and socket errors) and `ValueError` become the unknown reason. Decided 2026-10-13 at create-prd (discovery Open Questions): parser `cryptography`, extra name `sysup-cert`, declared as `sysup-cert = ["cryptography>=42,<51"]` in `pyproject.toml:27-40` (42 introduced `not_valid_after_utc`; 50.0.2 is what `uv.lock` resolves today) and added to the `all` extra; the README extras table (`README.md:72-83`) gets the row `sysup-cert | cryptography | sysup (x509-expiry)`. No bundled item (Q8); SSH certificates (OpenSSH, not X.509) stay out of scope.
  The tool manifest's requirements block (`src/tools/sysup/manifest.toml:14-16`) lists the extra as well.

### Capability: Item checks in the run
Every ordinary run checks every applicable item before any command.

#### Feature: Classification
- **Description**: One `StepResult` per item, status `ok` / `expiring` / `expired` / `unknown`.
- **Inputs**: item name, the capability outcome, `warn_days`, `now`.
- **Outputs**: final text of `classify_expiry` in `src/tools/sysup/runner.py`:

```python
def classify_expiry(name: str, outcome: datetime | str, warn_days: int, now: datetime) -> StepResult:
    if isinstance(outcome, str):
        return StepResult(name, success=False, message=f"{name}: unknown, {outcome}", status="unknown", command=name, kind="item")
    day = outcome.astimezone(timezone.utc).date().isoformat()
    if outcome <= now:
        return StepResult(name, success=False, message=f"{name}: expired on {day}", status="expired", command=name, kind="item")
    days_left = (outcome.astimezone(timezone.utc).date() - now.astimezone(timezone.utc).date()).days
    if days_left <= warn_days:
        return StepResult(name, success=True, message=f"{name}: expiring in {days_left} days ({day})", status="expiring", command=name, kind="item")
    return StepResult(name, success=True, message=f"{name}: ok, expires {day} ({days_left} days)", command=name, kind="item")
```

- **Behavior**: `days_left` is a UTC calendar-day difference, so exactly `warn_days` days left is amber and the day of expiry is amber until the instant passes. `_report_step` in `cli.py` renders `expiring` through `console.warning` (today it maps `success` to success/failure only, `src/tools/sysup/cli.py:19-23`).

#### Feature: Pre-pass before prime and commands
- **Description**: `Runner.run` yields the item results first, then primes, then runs the selected commands; `--only` and `--tag` never filter items.
- **Inputs**: `applicable_items(self._cfg)`.
- **Outputs**: `Runner.check_items(items) -> Iterator[StepResult]`, public so `sysup refresh` can re-check one item; it also records each item's status in `self._item_status` for gating.
- **Behavior**: inside the existing `try` of `run` (`src/tools/sysup/runner.py:36-51`): `if not self._dry_run: yield from self.check_items(applicable_items(self._cfg)); stops = self._prime()`. Decided 2026-10-13 at create-prd: items run before `_prime` so a read-only probe never waits on a sudo prompt and an interrupt during probing has no refresher to release. Under `--dry-run` no item is probed and no gating applies (A7, Q11).

#### Feature: `needs:` gating
- **Description**: A command whose needed item is `expired` or `unknown` this run does not run and reports a failed step naming the refresh command.
- **Inputs**: `command.needs`, `self._item_status`.
- **Outputs**: `StepResult(name, success=False, message=f"{name} skipped: {item} is {status}; run: sysup refresh {item}", command=name)` for the first blocking item, in `_run_entry` before the `use` / `steps` dispatch (`src/tools/sysup/runner.py:61-65`).
- **Behavior**: `ok` and `expiring` items never block. An item that was not checked this run (disabled, or `when` mismatch on this host) does not block either; decided 2026-10-13 at create-prd, since gating on an unchecked item would turn a disabled template into a permanent skip.

### Capability: Guided refresh
`sysup refresh <item>` walks the human through renewal on a terminal and re-checks.

#### Feature: Run the refresh commands
- **Description**: `run_refresh(name, spec, read_secret)` in `src/tools/sysup/refresh.py` runs the procedure's commands in order and stops at the first failure.
- **Inputs**: the item name, its `RefreshSpec`, a `read_secret` callable (the CLI passes the stdlib `getpass` prompt; tests pass a lambda).
- **Outputs**: one `StepResult` with `kind="item"`: success `"<name>: refresh commands completed"`, or failure `"<binary> not found"` / `"<argv joined> failed: exit code <rc>"`.
- **Behavior**: per command, `shutil.which(argv[0])` immediately before the spawn; env is `{**os.environ, **{k: os.path.expanduser(v) for k, v in command.env.items()}}`; `read_secret()` is called only when `command.stdin == "secret"`, and only then does `subprocess.run([binary, *argv[1:]], env=env, input=secret, text=True, check=False)` receive input, so a procedure without that declaration never prompts (Q9); the secret local is deleted right after the call and is never logged, printed, stored or sent. Commands without a secret inherit the terminal (no capture), so `gh auth login` can print.

#### Feature: `sysup refresh <item>` subcommand
- **Description**: Terminal-only subcommand on the group from PRD 00092.
- **Inputs**: the item name argument; `load_config` through `ctx.obj` like the run path.
- **Outputs**: exit 1 with `sysup refresh needs a terminal` when `_is_tty()` (a one-line wrapper over `sys.stdin.isatty()`, patched in tests) is false; `unknown expiry item '<item>'`, `item '<item>' is disabled; enable it in buvis-sysup.local.yaml first`, `item '<item>' has no refresh procedure` as panics; otherwise the instructions via `console.print(..., mode="raw")`, `press Enter when done` via `console.info`, one `input()` for the pause, then `run_refresh` with `getpass.getpass("paste the new secret: ")` as the reader.
- **Behavior**: a failed procedure is reported through `_report_step` and exits 1 without re-checking. After success the item is re-checked with `Runner(cfg).check_items([(item, spec)])`, reported with `_report_step`, folded with `fold_results(read_state(), {item}, recheck, now)` and written with `write_state`; only an `ok` recheck removes the entry, `expiring`, `expired` and `unknown` update it (Q3: a refresh is not evidence of recovery). Exit code follows `exit_code(recheck)`. No notification is sent from `refresh` (decided 2026-10-13 at create-prd: the user is at the terminal watching the result). `refresh` never runs inside a plain `sysup` pass.

### Capability: CLI integration
The ordinary run folds items into the same record and points at the refresh.

#### Feature: Items count as checked
- **Description**: the `checked` set passed to `fold_results` includes every applicable item name on an ordinary run.
- **Inputs**: `applicable_items(cfg)`.
- **Outputs**: `checked = {name for name, _ in plan} | {name for name, _ in applicable_items(cfg)}`.
- **Behavior**: a filtered run therefore still clears an item entry whose check came back `ok` and still updates one that did not.

#### Feature: Refresh hint in summary and status
- **Description**: `_entry_line` from PRD 00092 appends `; run: sysup refresh <name>` for entries with `kind == "item"`.
- **Inputs**: the entry's `kind`.
- **Outputs**: the summary and `sysup status` lines.
- **Behavior**: the shape test from PRD 00092 becomes `test_cli_is_a_group_with_status_and_refresh` asserting `set(cli.commands) == {"refresh", "status"}`.

## Structural Decomposition

### Repository Structure

```
src/tools/sysup/
├── config.py                       # Maps to: Expiry registry in config (models, _validate_expiry, applicable_items, _applies, needs)
├── default.yaml                    # Maps to: Bundled gh-agent template
├── capabilities/
│   ├── __init__.py                 # Maps to: ExpiryCapability protocol, EXPIRY_CAPABILITIES
│   ├── gh_token.py                 # NEW: Maps to: gh-token-expiry
│   └── x509.py                     # NEW: Maps to: x509-expiry
├── runner.py                       # Maps to: Item checks in the run (classify_expiry, check_items, needs gating)
├── refresh.py                      # NEW: Maps to: Run the refresh commands
├── cli.py                          # Maps to: refresh subcommand, items checked, refresh hint
└── manifest.toml                   # extras = ["sysup-cert"]
tests/tools/sysup/
├── test_config.py                  # expiry, needs, collision, required-input tests added
├── test_default_config.py          # template test added
├── test_gh_token.py                # NEW
├── test_x509.py                    # NEW (import-skip guarded)
├── test_runner.py                  # pre-pass, dry-run, gating tests added
├── test_refresh.py                 # NEW
└── test_sysup_cli.py               # refresh and item tests added; shape test updated
docs/source/tools/sysup.rst         # Expiry items section, capabilities table rows, refresh usage
README.md                           # extras table row
CHANGELOG.md                        # Added entry
pyproject.toml                      # sysup-cert extra, all extra
```

### Module: sysup.config
- **Maps to capability**: Expiry registry in config
- **Responsibility**: Models, the five validation rules, `applicable_items`, the shared `_applies` guard, `needs` on commands.
- **Exports**: `ExpiryItem`, `RefreshCommand`, `RefreshSpec`, `applicable_items` added to `__all__`
- New symbols: `ExpiryItem`, `RefreshCommand`, `RefreshSpec`, `applicable_items`, `_applies`, `_validate_expiry`, `warn_days`, `with_`, `expiry`

### Module: sysup.capabilities
- **Maps to capability**: Expiry capabilities
- **Responsibility**: The protocol, the registry, and the two probes; no console output and no process exit. The invariant test globs every file under the capabilities directory (`tests/tools/sysup/test_invariants.py:12-16`).
- **Exports**: `ExpiryCapability`, `EXPIRY_CAPABILITIES`, `GhTokenExpiry`, `X509Expiry`, `parse_expiration`
- New symbols: `ExpiryCapability`, `EXPIRY_CAPABILITIES`, `GhTokenExpiry`, `X509Expiry`, `parse_expiration`, `expires_at`, `gh_token.py`, `x509.py`, `GH_CONFIG_DIR`, `get_server_certificate`, `not_valid_after_utc`, `expiring`, `expired`

### Module: sysup.runner
- **Maps to capability**: Item checks in the run
- **Responsibility**: `classify_expiry`, `check_items`, the pre-pass placement, `_item_status`, `needs` gating in `_run_entry`.
- **Exports**: `check_items` on `Runner`, `classify_expiry`
- New symbols: `classify_expiry`, `check_items`, `_check_items`, `_item_status`, `days_left`, `Runner.check_items`, `self._item_status`

### Module: sysup.refresh
- **Maps to capability**: Guided refresh
- **Responsibility**: Run a refresh procedure with the secret confined to one stdin; return one `StepResult`; no console output.
- **Exports**: `run_refresh`
- New symbols: `run_refresh`, `read_secret`, `refresh.py`

### Module: sysup.cli
- **Maps to capability**: Guided refresh, CLI integration
- **Responsibility**: The `refresh` subcommand (TTY check, config lookup, instructions, pause, procedure, recheck, fold, exit code), the item-inclusive `checked` set, the `expiring` rendering in `_report_step`, the refresh hint in `_entry_line`.
- **Exports**: subcommand `refresh`
- New symbols: `_is_tty`, `_entry_line`, `fold_results`, `sysup.cli._is_tty`, `SysupConfig.expiry`, `sysup.capabilities.gh_token`, `sysup.capabilities.x509.ssl.get_server_certificate`
- `_entry_line` and `fold_results` are created by PRD 00092 and only extended or called here.

### Module: tests
- **Maps to capability**: all
- **Responsibility**: `test_gh_token.py` patches `shutil.which` and `subprocess.run` in `sysup.capabilities.gh_token` with `CompletedProcess` values whose stdout carries the measured header line, asserts `GH_CONFIG_DIR` in the call's `env` and absent from `args`, and drives `classify_expiry` through `parse_expiration` for dates 40, 30, 1 and -1 days from a fixed `now` with `warn_days=30`. `test_x509.py` starts with `pytest.importorskip("cryptography")` for the two certificate tests, builds a self-signed certificate with `cryptography.x509.CertificateBuilder` and an `ec` key, writes it as PEM under `tmp_path`, and patches `sysup.capabilities.x509.ssl.get_server_certificate` for the host case; `test_missing_extra_reports_unknown_with_install_hint` sets `sys.modules["cryptography"]` to `None` through `monkeypatch.setitem` so the lazy import raises `ImportError`. `test_refresh.py` patches `sysup.refresh.subprocess.run` and `sysup.refresh.shutil.which` and asserts `input="tok"` only on the declaring command, `"tok"` absent from every `args` and `env` value, and no `read_secret` call for a procedure without `stdin: secret`. CLI refresh tests patch `sysup.cli._is_tty`, `sysup.refresh.subprocess.run`, `getpass.getpass` and the registry entry, and invoke with `input="\n"`.
- **Exports**: none
- New symbols: `test_header_date_maps_to_ok_expiring_expired_around_warn_days`, `test_probe_denied_reports_unknown_grant_broken`, `test_missing_gh_reports_unknown`, `test_config_dir_is_passed_as_env_not_argv`, `test_missing_header_reports_unknown`, `test_pem_file_not_after`, `test_host_port_uses_get_server_certificate`, `test_missing_extra_reports_unknown_with_install_hint`, `test_exactly_one_of_path_or_host`, `test_secret_goes_only_to_stdin_of_the_declaring_command`, `test_no_secret_prompt_without_stdin_secret`, `test_failed_command_stops_and_reports_exit_code`, `test_env_values_are_tilde_expanded`, `test_items_are_checked_before_prime_and_commands`, `test_dry_run_skips_item_probes`, `test_needs_expired_item_skips_command_with_refresh_hint`, `test_needs_unknown_item_skips_command`, `test_needs_ok_or_expiring_item_runs_command`, `test_capability_exception_becomes_unknown`, `test_refresh_refuses_without_tty`, `test_refresh_runs_procedure_then_rechecks_and_clears_on_ok`, `test_refresh_recheck_not_ok_keeps_entry_and_exits_1`, `test_refresh_disabled_item_is_refused`, `test_filtered_run_still_checks_every_item`, `test_summary_adds_refresh_hint_for_items`, `test_expiry_item_validates_with_defaults`, `test_enabled_gh_item_without_probe_is_rejected`, `test_disabled_template_without_probe_loads`, `test_unknown_expiry_capability_rejected`, `test_needs_unknown_item_rejected`, `test_item_and_command_name_collision_rejected`, `test_gh_agent_template_is_disabled_and_has_no_probe`, `test_cli_is_a_group_with_status_and_refresh`

### Module: docs, packaging and changelog
- **Maps to capability**: all (user-facing description)
- **Responsibility**: `docs/source/tools/sysup.rst` gains `sysup refresh gh-agent` in the Usage block and a section titled Expiry items after the Attention section from PRD 00092: the `expiry:` map with every field, that items run before commands on every ordinary run and never under `--list` / `--dry-run` / `status`, the `needs:` rule, how to enable the bundled `gh-agent` template from `buvis-sysup.local.yaml`, and the `sysup-cert` extra.
  The built-in capabilities table (`docs/source/tools/sysup.rst:91-107`) gets two rows: `gh-token-expiry` (inputs `config_dir`, `probe`; expiry header plus private-repo grant probe) and `x509-expiry` (one of `path`, `host`; needs the `sysup-cert` extra). `pyproject.toml` extras, `manifest.toml`, and the README row as specified above. `CHANGELOG.md` under `[Unreleased]` `### Added`: `**sysup**: an `expiry:` registry of credentials with a hard expiry, checked before every ordinary run and fed into the attention summary, state, push and exit code: built-in `gh-token-expiry` (expiration header plus a private-repository grant probe; a disabled `gh-agent` template ships, enable it locally with your probe) and `x509-expiry` (PEM file or TLS endpoint, needs the new `sysup-cert` extra); commands can declare `needs: [item]` and are skipped with a `sysup refresh <item>` hint while the item is expired or unknown; `sysup refresh <item>` walks through renewal on a terminal, passes a pasted secret only on the stdin of the command that declares `stdin: secret`, and re-checks the item`.
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies inside this PRD - built first (PRD 00092 is a precondition: `StepResult.status` / `kind`, `sysup.attention`, the CLI group).

- **sysup.config**: models, validation, `applicable_items`, the template.
- **sysup.capabilities**: protocol, registry, `gh_token.py`, `x509.py`; packaging rows.

### Core Layer (Phase 1)
- **sysup.runner**: Depends on [sysup.config, sysup.capabilities].
- **sysup.refresh**: Depends on [sysup.config] (`RefreshSpec`).

### Integration Layer (Phase 2)
- **sysup.cli**: Depends on [sysup.runner, sysup.refresh, sysup.config, sysup.attention (PRD 00092)].
- **docs, packaging and changelog**: Depends on [sysup.cli].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Config can declare items and the two probes exist, each with its own tests.

**Tasks**:
- [ ] Add `RefreshCommand`, `RefreshSpec`, `ExpiryItem`, `SysupCommand.needs`, `SysupConfig.expiry`, `_applies`, `applicable_items`, `_validate_expiry` to `src/tools/sysup/config.py`; append the template to `default.yaml`; add the seven named config tests (no deps). Premise, re-checked at execution: `rg -c "    def test_" tests/tools/sysup/test_config.py` prints 23 (21 today plus the two ntfy tests PRD 00092 adds); otherwise stop and report. Acceptance: the count prints at least 30; `uv run pytest tests/tools/sysup/test_config.py tests/tools/sysup/test_default_config.py -q` passes; `uv run pytest tests/tools/sysup/test_default_config.py -q -k darwin_plan` still passes unchanged (the template adds no command).
- [ ] Add `ExpiryCapability` and `EXPIRY_CAPABILITIES` to `src/tools/sysup/capabilities/__init__.py`, create `gh_token.py` and `x509.py`, add the `sysup-cert` extra to `pyproject.toml` (and to `all`), the manifest `extras` entry and the README row; add `tests/tools/sysup/test_gh_token.py` and `tests/tools/sysup/test_x509.py` (no deps) - Acceptance: `uv run pytest tests/tools/sysup/test_gh_token.py tests/tools/sysup/test_x509.py tests/tools/sysup/test_invariants.py -q` passes; the tomllib assertion from Success Metrics exits 0; `uv run python -c "import sysup.capabilities.x509"` exits 0 (lazy import).

**Exit Criteria**: `uv run pytest tests/tools/sysup -q` passes.

### Phase 1: Core
**Goal**: Runs check items first and gate on them; a refresh procedure runs with the secret confined.

**Tasks**:
- [ ] Add `classify_expiry`, `Runner.check_items`, `_check_items`, `_item_status`, the pre-pass in `run`, and the gating in `_run_entry` to `src/tools/sysup/runner.py`; add the six named runner tests, with `test_items_are_checked_before_prime_and_commands` recording the order `item`, `primed`, `step` the way `test_prime_runs_before_commands` does today (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/sysup/test_runner.py -q` passes.
- [ ] Create `src/tools/sysup/refresh.py` with `run_refresh` and `tests/tools/sysup/test_refresh.py` with the four named tests (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/sysup/test_refresh.py -q` passes; `rg -n "print\(|console\." src/tools/sysup/refresh.py` prints nothing.

**Exit Criteria**: `uv run pytest tests/tools/sysup -q` passes.

### Phase 2: Integration
**Goal**: The CLI exposes `refresh`, folds items, and the docs describe the registry.

**Tasks**:
- [ ] Add `_is_tty`, the `refresh` subcommand, the item-inclusive `checked` set, the `expiring` branch in `_report_step` and the refresh hint in `_entry_line` to `src/tools/sysup/cli.py`; rename the shape test and add the six named CLI tests (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/sysup/test_sysup_cli.py -q` passes; `test_refresh_runs_procedure_then_rechecks_and_clears_on_ok` asserts the patched `subprocess.run` received `input="tok"` on the secret command, that `"tok"` appears in no `args` and no `env` value, that the seeded `gh-agent` entry is gone from the state file after an `ok` recheck, and exit 0; `test_refresh_refuses_without_tty` asserts exit 1, `needs a terminal` in the output and `subprocess.run` never called.
- [ ] Update `docs/source/tools/sysup.rst`, `README.md` and `CHANGELOG.md` as specified in the docs module (depends on: previous task) - Acceptance: `rg -c "sysup refresh" docs/source/tools/sysup.rst` prints at least 2; `rg -c "sysup-cert" README.md CHANGELOG.md docs/source/tools/sysup.rst` prints 1 for each file; `uv run sphinx-build -b html docs/source docs/build/html -q` exits 0.

**Exit Criteria**: `uv run pytest -m sysup -q` green; `uv run mypy src/tools/sysup` clean; `uv run ruff check src/tools/sysup tests/tools/sysup` clean; `rg -n "noqa" src/tools/sysup/capabilities/gh_token.py src/tools/sysup/capabilities/x509.py src/tools/sysup/refresh.py` prints nothing.

## Test Strategy

### Critical Scenarios
- **Happy path**: enabled `gh-agent` with a probe, header 300 days out, probe succeeds -> Expected: `gh-agent: ok, expires <day> (300 days)` printed before any command line, no entry, exit 0.
- **Happy path**: header 12 days out -> Expected: `expiring in 12 days`, amber entry with `kind: item`, one push on the first run only, exit 0.
- **Edge case**: header exactly `warn_days` days out -> Expected: amber; `warn_days + 1` -> ok.
- **Edge case**: `sysup --only brew` with an applicable item -> Expected: the item is still probed and folded; `brew` runs; `helm` stays retained.
- **Edge case**: a command with `needs: [gh-agent]` while `gh-agent` is `expiring` -> Expected: runs normally.
- **Error case**: the probe exits 1 (`HTTP 404`) -> Expected: `gh-agent: unknown, grant broken: gh api repos/x/y: ...`, red entry, exit 1, push body names it.
- **Error case**: a command with `needs: [gh-agent]` while `gh-agent` is `expired` -> Expected: `<name> skipped: gh-agent is expired; run: sysup refresh gh-agent`, no subprocess for that command, exit 1.
- **Error case**: `sysup refresh gh-agent` piped (no TTY) -> Expected: `sysup refresh needs a terminal`, exit 1, nothing run.
- **Error case**: refresh command exits 1 -> Expected: `gh auth login --with-token --insecure-storage failed: exit code 1`, no recheck, entry untouched, exit 1.
- **Error case**: x509 item on a core-only install -> Expected: `unknown, x509-expiry needs the sysup-cert extra: ...`, red entry, exit 1; gh tracking in the same run unaffected.

## Risks

- **Network blip reads as red** (accepted, Q6): the unknown message names `gh api <probe>` and gh's stderr, so a transient failure is recognisable; the next run clears it.
- **Tracking stays off until configured**: the template is disabled and needs a local probe and `enabled: true`. Mitigation: the docs section shows the exact `buvis-sysup.local.yaml` snippet; `sysup --list` does not show items, so the Expiry section tells the user to run a plain `sysup` and look for the `gh-agent:` line.
- **Secret leakage**: the secret exists only as a local in `run_refresh`, passed through `input=`; tests assert its absence from `args` and `env`; `refresh.py` has no console or print call (acceptance grep). Not covered: a refresh command that itself echoes stdin.
- **`cryptography` version drift**: `not_valid_after_utc` needs 42+; the extra floors it; `uv.lock` already resolves 50.0.2 for dev, so tests run in CI with `--all-extras`.
- **`gh api -i` output shape**: the header line is matched case-insensitively at a line start; a `--silent` probe prints no body. If GitHub ever drops the header, the item reads `unknown` with an explicit reason rather than `ok`.
- **Name collisions between commands and items**: rejected at load; entries in `attention.json` are keyed by name only (PRD 00092), so this rule is what keeps them unambiguous.
- **Neighbouring sysup PRDs**: premises pin the `def test_` count of `test_config.py` only, never a suite total.

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Annotated, Literal

import yaml
from buvis.pybase.configuration import (
    ConfigurationError,
    ConfigurationLoader,
    MissingEnvVarError,
)
from buvis.pybase.result import FatalError
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator

from sysup.capabilities import CAPABILITIES, EXPIRY_CAPABILITIES
from sysup.settings import SysupSettings

__all__ = [
    "ExpiryItem",
    "NtfySpec",
    "RefreshCommand",
    "RefreshSpec",
    "StepSpec",
    "SysupCommand",
    "SysupConfig",
    "WhenSpec",
    "applicable_commands",
    "applicable_items",
    "load_config",
]

_DEFAULT_CONFIG_RESOURCE = "default.yaml"


class WhenSpec(BaseModel):
    """Applicability guard for a command entry.

    ``os`` is matched against :data:`sys.platform`; ``check`` names a binary that
    must resolve via :func:`shutil.which` at run time for the entry to apply.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    os: Literal["darwin", "linux", "win32"] | None = None
    check: str | None = None


class NtfySpec(BaseModel):
    """Optional ntfy endpoint, topic and Basic-auth credentials file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str | None = None
    topic: str | None = None
    credentials_file: str | None = None


_SHELL = ("bash", "-eo", "pipefail", "-c")


def _shell_or_argv(value: object) -> object:
    """A string is one ``bash -eo pipefail -c`` script; anything else is argv as given."""
    if not isinstance(value, str):
        return value
    if not value.strip():
        msg = "a shell step cannot be empty"
        raise ValueError(msg)
    return [*_SHELL, value]


def _as_step(value: object) -> object:
    """Accept a bare shell line or argv list as sugar for ``{argv: <value>}``."""
    if isinstance(value, (str, list, tuple)):
        return {"argv": value}
    if isinstance(value, dict) and "argv" not in value:
        msg = (
            "a step is a shell line, an argv list or an {argv, env} object; "
            "quote a shell line that contains ': ' or ' #'"
        )
        raise ValueError(msg)
    return value


class StepSpec(BaseModel):
    """One program to spawn: ``argv`` plus ``env`` merged over the parent
    environment. A string ``argv`` is a shell line run by ``bash -eo pipefail -c``.
    Shared by run-entry steps and refresh commands."""

    model_config = ConfigDict(extra="forbid", frozen=True, coerce_numbers_to_str=True)

    argv: Annotated[tuple[str, ...], BeforeValidator(_shell_or_argv)] = Field(..., min_length=1)
    env: dict[str, str] = {}

    @property
    def label(self: StepSpec) -> str:
        """The step as written: a shell line's text, else its argv joined."""
        if len(self.argv) == len(_SHELL) + 1 and self.argv[: len(_SHELL)] == _SHELL:
            return self.argv[-1]
        return " ".join(self.argv)

    def child_env(self: StepSpec) -> dict[str, str]:
        """Return the parent environment with ``env`` merged on top, ``~`` expanded.

        ``os.environ`` itself is never mutated.
        """
        return {**os.environ, **{key: os.path.expanduser(value) for key, value in self.env.items()}}


class SysupCommand(BaseModel):
    """One updater entry: exactly one of ``steps`` (a sequence of :class:`StepSpec`,
    each written as a shell line, a bare argv list or an ``{argv, env}`` object)
    or ``use`` (named capability + optional ``with:`` inputs)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    order: int = 100
    enabled: bool = True
    when: WhenSpec = WhenSpec()
    interactive: bool = False
    timeout: int | None = None
    continue_on_error: bool = False
    sudo: bool = False
    tags: tuple[str, ...] = ()
    steps: tuple[Annotated[StepSpec, BeforeValidator(_as_step)], ...] | None = None
    use: str | None = None
    with_: dict[str, object] = Field(default_factory=dict, alias="with")
    needs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _exactly_one_kind(self: SysupCommand) -> SysupCommand:
        if bool(self.steps) == bool(self.use):
            msg = "entry must have exactly one of `steps` or `use`"
            raise ValueError(msg)
        return self


class RefreshCommand(StepSpec):
    """A :class:`StepSpec` that may also take the pasted secret on stdin."""

    stdin: Literal["secret"] | None = None


class RefreshSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    instructions: str
    commands: tuple[Annotated[RefreshCommand, BeforeValidator(_as_step)], ...] = ()


class ExpiryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    use: str
    with_: dict[str, object] = Field(default_factory=dict, alias="with")
    warn_days: int = 30
    refresh: RefreshSpec | None = None
    enabled: bool = True
    when: WhenSpec = WhenSpec()


class SysupConfig(BaseModel):
    """The whole merged, validated sysup configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commands: dict[str, SysupCommand] = {}
    prime: tuple[str, ...] = ()
    ntfy: NtfySpec = NtfySpec()
    expiry: dict[str, ExpiryItem] = {}


# Sysup's own top-level config keys. The shared config stack (config.yaml /
# buvis.yaml) carries other tools' and global fields; only these plan keys are
# projected into SysupConfig, whose extra="forbid" would otherwise reject them.
_SYSUP_TOP_LEVEL_KEYS = frozenset(SysupConfig.model_fields)
_SYSUP_SETTINGS_KEYS = frozenset(SysupSettings.model_fields)


def _is_sysup_specific(path: Path) -> bool:
    """Whether ``path`` is a sysup-specific config file (``buvis-sysup*.yaml``).

    A sysup-specific file should carry only sysup's plan keys plus the global
    settings keys, so an unknown top-level key in it is a typo. A shared file
    (``config.yaml`` / ``buvis.yaml``) legitimately carries other tools' +
    global keys and is not checked.
    """
    return path.name.startswith("buvis-sysup")


def _unknown_top_level_keys(data: dict[str, object]) -> set[str]:
    """Return top-level keys in ``data`` that are not sysup's.

    A key may carry a ``+`` / ``-`` directive suffix, so the suffix is stripped
    before the membership check.
    """
    allowed = _SYSUP_TOP_LEVEL_KEYS | _SYSUP_SETTINGS_KEYS
    unknown: set[str] = set()
    for key in data:
        base = key[:-1] if key.endswith(("+", "-")) else key
        if base not in allowed:
            unknown.add(key)
    return unknown


def _format_validation_errors(exc: ValidationError, key_sources: dict[tuple[str, ...], Path]) -> str:
    """One ``<source>: <dotted location>: <message>`` line per pydantic error.

    The source is the config file that last set the entry (``commands.name``),
    else the top-level key, else ``bundled default``. ``str(exc)`` is never
    used — it embeds the pydantic documentation URL.
    """
    parts: list[str] = []
    for error in exc.errors():
        loc = error["loc"]
        entry = tuple(str(part) for part in loc[:2])
        source = key_sources.get(entry) or key_sources.get(entry[:1]) or "bundled default"
        parts.append(f"{source}: {'.'.join(str(part) for part in loc)}: {error['msg']}")
    return "; ".join(parts)


def _validate_capabilities(cfg: SysupConfig) -> None:
    """Reject unknown ``use:`` names and unknown ``with:`` inputs.

    Raises:
        FatalError: on an unknown capability name or an unknown ``with:`` input
            for a known capability.
    """
    for name, command in cfg.commands.items():
        if command.use is None:
            continue
        capability = CAPABILITIES.get(command.use)
        if capability is None:
            msg = f"command '{name}': unknown capability '{command.use}'"
            raise FatalError(msg)
        accepted = set(capability.inputs)
        unknown = set(command.with_) - accepted
        if unknown:
            allowed = ", ".join(sorted(accepted)) or "(none)"
            msg = (
                f"command '{name}': capability '{command.use}' got unknown "
                f"input(s) {', '.join(sorted(unknown))}; accepted: {allowed}"
            )
            raise FatalError(msg)
    for name in cfg.prime:
        capability = CAPABILITIES.get(name)
        if capability is None:
            msg = f"prime: unknown capability '{name}'"
            raise FatalError(msg)


def _validate_expiry(cfg: SysupConfig) -> None:
    """Validate the expiry registry and the ``needs:`` references.

    Rules, each raising :class:`FatalError` with one clear message:

    * unknown expiry capability on an item;
    * unknown ``with:`` input for a known capability;
    * a required input (capability default ``None``) absent, ``None`` or empty
      on an *enabled* item (disabled items skip this, so the bundled template
      can ship without a probe);
    * a name used by both a command and an expiry item;
    * a command ``needs:`` naming an item that does not exist.

    Raises:
        FatalError: on any violated rule.
    """
    for name, item in cfg.expiry.items():
        capability = EXPIRY_CAPABILITIES.get(item.use)
        if capability is None:
            msg = f"item '{name}': unknown expiry capability '{item.use}'"
            raise FatalError(msg)
        accepted = set(capability.inputs)
        unknown = set(item.with_) - accepted
        if unknown:
            allowed = ", ".join(sorted(accepted)) or "(none)"
            msg = (
                f"item '{name}': capability '{item.use}' got unknown "
                f"input(s) {', '.join(sorted(unknown))}; accepted: {allowed}"
            )
            raise FatalError(msg)
        if item.enabled:
            for key, default in capability.inputs.items():
                if default is None and not item.with_.get(key):
                    msg = f"item '{name}': capability '{item.use}' requires input '{key}' before it can be enabled"
                    raise FatalError(msg)

    for name in cfg.expiry:
        if name in cfg.commands:
            msg = f"'{name}' is both a command and an expiry item"
            raise FatalError(msg)

    for name, command in cfg.commands.items():
        for needed in command.needs:
            if needed not in cfg.expiry:
                msg = f"command '{name}': needs unknown expiry item '{needed}'"
                raise FatalError(msg)


def _load_default() -> dict[str, object]:
    """Load the bundled ``default.yaml`` as the lowest-priority layer.

    Anchored to this module's own file rather than resolved by package name:
    under pytest's importlib mode the ``sysup`` name is a namespace shared with
    the test package, so ``importlib.resources.files("sysup")`` can resolve to
    the wrong path entry. ``default.yaml`` always ships beside this module in the
    wheel (hatch packages the whole ``sysup`` directory), so its own directory is
    the unambiguous anchor.
    """
    resource = Path(__file__).with_name(_DEFAULT_CONFIG_RESOURCE)
    text = resource.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _merge_layer(merged: dict[str, object], path: Path, key_sources: dict[tuple[str, ...], Path]) -> dict[str, object]:
    """Load one user config file, check its keys and merge it over ``merged``.

    Records in ``key_sources`` which file last set each top-level plan key and,
    for mapping keys (``commands``, ``expiry``), each entry under it.

    Raises:
        FatalError: on a load or merge failure, or an unknown top-level key in a
            sysup-specific file.
    """
    try:
        data = ConfigurationLoader.load_yaml(path)
    except (yaml.YAMLError, MissingEnvVarError, OSError, UnicodeError) as exc:
        msg = f"{path}: {exc}"
        raise FatalError(msg) from exc
    # A sysup-SPECIFIC file (buvis-sysup*.yaml) should carry only sysup's
    # keys, so an unknown top-level key there is a typo (comands:, primey:)
    # to reject — the projection would otherwise silently drop it and run the
    # bundled plan. A SHARED file (config.yaml / buvis.yaml) legitimately
    # carries other tools' + global keys, so its extras are tolerated.
    if _is_sysup_specific(path):
        unknown = _unknown_top_level_keys(data)
        if unknown:
            allowed = ", ".join(sorted(_SYSUP_TOP_LEVEL_KEYS | _SYSUP_SETTINGS_KEYS))
            msg = (
                f"unknown key(s) in {path}: {', '.join(sorted(unknown))}; "
                f"sysup config accepts only: {allowed} (with +/- directive suffixes on list keys)"
            )
            raise FatalError(msg)
    try:
        result = ConfigurationLoader.merge_configs(merged, data)
    except (ConfigurationError, yaml.YAMLError, MissingEnvVarError) as exc:
        msg = f"{path}: {exc}"
        raise FatalError(msg) from exc
    for key, value in data.items():
        base = key[:-1] if key.endswith(("+", "-")) else key
        if base in _SYSUP_TOP_LEVEL_KEYS:
            key_sources[(base,)] = path
            if isinstance(value, dict):
                key_sources.update({(base, str(name)): path for name in value})
    return result


def load_config(config_dir: str | None = None, config_path: str | None = None) -> SysupConfig:
    """Merge the bundled default with user config files and validate.

    Layers, lowest priority first: the bundled ``default.yaml``, then the user
    files returned by :meth:`ConfigurationLoader.find_config_files_ranked`
    (already low-to-high — never reverse it). An explicit ``config_path`` (from
    ``--config FILE``) is the single highest-priority layer. Each file is
    merged by :func:`_merge_layer` (later wins). A sysup-specific file
    (``buvis-sysup*.yaml``) may carry only plan keys plus global settings keys;
    a shared file may carry any key, and its extras are dropped by the
    projection. The merged document is projected onto sysup's plan keys,
    validated against :class:`SysupConfig` (each error attributed to the file
    that set the key), then checked against the capability registry.

    Args:
        config_dir: Explicit config directory (from ``--config-dir``), threaded
            from the CLI so the plan is discovered under the SAME directory the
            settings were resolved from.
        config_path: Explicit config file (from ``--config``), so
            ``sysup --config FILE`` runs the plan from FILE.

    Raises:
        FatalError: on malformed YAML in a config file, a merge/directive error,
            a missing required env var, an unknown top-level key in a
            sysup-specific file, an invalid schema, an unknown capability, or an
            unknown ``with:`` input — every failure the CLI's ``FatalError``
            handler can render, never a raw traceback.
    """
    merged: dict[str, object] = _load_default()
    key_sources: dict[tuple[str, ...], Path] = {}
    ranked_files: list[Path] = ConfigurationLoader.find_config_files_ranked(
        "sysup", config_dir=config_dir, config_path=config_path
    )
    for path in ranked_files:
        merged = _merge_layer(merged, path, key_sources)

    projected = {key: value for key, value in merged.items() if key in _SYSUP_TOP_LEVEL_KEYS}

    try:
        cfg = SysupConfig.model_validate(projected)
    except ValidationError as exc:
        msg = f"invalid sysup configuration: {_format_validation_errors(exc, key_sources)}"
        raise FatalError(msg) from exc

    _validate_capabilities(cfg)
    _validate_expiry(cfg)
    return cfg


def _applies(entry: SysupCommand | ExpiryItem) -> bool:
    """Return whether an enabled entry's ``when`` guard matches this host.

    An entry applies when it is ``enabled``, its ``when.os`` (if set) equals
    :data:`sys.platform`, and its ``when.check`` binary (if set) resolves via
    :func:`shutil.which`.
    """
    if not entry.enabled:
        return False
    if entry.when.os is not None and entry.when.os != sys.platform:
        return False
    return not (entry.when.check is not None and shutil.which(entry.when.check) is None)


def applicable_commands(cfg: SysupConfig) -> list[tuple[str, SysupCommand]]:
    """Return enabled entries whose ``when`` matches this host, sorted by
    ``(order, name)``.

    An entry is applicable when it is ``enabled``, its ``when.os`` (if set)
    equals :data:`sys.platform`, and its ``when.check`` binary (if set) resolves
    via :func:`shutil.which`.
    """
    applicable = [(name, command) for name, command in cfg.commands.items() if _applies(command)]
    applicable.sort(key=lambda item: (item[1].order, item[0]))
    return applicable


def applicable_items(cfg: SysupConfig) -> list[tuple[str, ExpiryItem]]:
    """Return enabled expiry items whose ``when`` matches this host, sorted by name."""
    applicable = [(name, item) for name, item in cfg.expiry.items() if _applies(item)]
    applicable.sort(key=lambda entry: entry[0])
    return applicable

from __future__ import annotations

from pathlib import Path

import yaml
from buvis.pybase.configuration import (
    ConfigurationError,
    ConfigurationLoader,
    MissingEnvVarError,
)
from buvis.pybase.result import FatalError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backup.capabilities import CAPABILITIES

__all__ = [
    "BackupConfig",
    "BackupInstance",
    "applicable_instances",
    "load_config",
]

_DEFAULT_CONFIG_RESOURCE = "default.yaml"

# Backup's own top-level config keys. The shared config stack (config.yaml /
# buvis.yaml) carries other tools' and global fields; only these are projected
# into BackupConfig, whose extra="forbid" would otherwise reject them.
_BACKUP_TOP_LEVEL_KEYS = frozenset({"instances", "excludes"})


def _is_backup_specific(path: Path) -> bool:
    """Whether ``path`` is a backup-specific config file (``buvis-backup*.yaml``).

    A backup-specific file should carry only backup's own keys, so an unknown
    top-level key in it is a typo. A shared file (``config.yaml`` / ``buvis.yaml``)
    legitimately carries other tools' + global keys and is not checked.
    """
    return path.name.startswith("buvis-backup")


def _unknown_top_level_keys(data: dict[str, object]) -> set[str]:
    """Return top-level keys in ``data`` that are not backup's.

    A list key may carry a ``+`` / ``-`` directive suffix (``excludes+`` /
    ``excludes-``, PRD 00080), so the suffix is stripped before the membership
    check. Non-mapping documents contribute nothing.
    """
    unknown: set[str] = set()
    for key in data:
        base = key[:-1] if key.endswith(("+", "-")) else key
        if base not in _BACKUP_TOP_LEVEL_KEYS:
            unknown.add(key)
    return unknown


class BackupInstance(BaseModel):
    """One configured backup capability instance.

    ``use`` names a registered capability, ``with:`` supplies its inputs, and
    ``tags`` group instances for ``--tag`` selection. ``enabled: false`` skips
    the instance without deleting it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    use: str
    enabled: bool = True
    order: int = 100
    tags: tuple[str, ...] = ()
    with_: dict[str, object] = Field(default_factory=dict, alias="with")


class BackupConfig(BaseModel):
    """The whole merged, validated backup configuration.

    ``instances`` is a name-keyed map of capability instances; ``excludes`` is
    the global basename exclude list that layers via 00080's ``excludes+`` /
    ``excludes-`` directives across gem -> user -> machine config.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    instances: dict[str, BackupInstance] = {}
    excludes: tuple[str, ...] = ()


def _validate_capabilities(cfg: BackupConfig) -> None:
    """Reject unknown ``use:`` names and unknown ``with:`` inputs.

    Raises:
        FatalError: on an unknown capability name or an unknown ``with:`` input
            for a known capability.
    """
    for name, instance in cfg.instances.items():
        capability = CAPABILITIES.get(instance.use)
        if capability is None:
            msg = f"instance '{name}': unknown capability '{instance.use}'"
            raise FatalError(msg)
        accepted = set(capability.inputs)
        unknown = set(instance.with_) - accepted
        if unknown:
            allowed = ", ".join(sorted(accepted)) or "(none)"
            msg = (
                f"instance '{name}': capability '{instance.use}' got unknown "
                f"input(s) {', '.join(sorted(unknown))}; accepted: {allowed}"
            )
            raise FatalError(msg)


def _load_default() -> dict[str, object]:
    """Load the bundled ``default.yaml`` as the lowest-priority layer.

    Anchored to this module's own file rather than resolved by package name:
    under pytest's importlib mode the ``backup`` name is a namespace shared with
    the test package, so ``importlib.resources.files("backup")`` can resolve to
    the wrong path entry. ``default.yaml`` always ships beside this module in the
    wheel (hatch packages the whole ``backup`` directory), so its own directory
    is the unambiguous anchor.

    Loaded through :meth:`ConfigurationLoader.load_yaml` — the SAME
    env-substituting loader the user layers use — so ``${HOME}`` (and the
    ``${VAR:-default}`` / ``$${VAR}`` escape forms) in the bundled defaults
    expand identically to user config. ``Path.expanduser`` only expands ``~``, so
    a raw ``yaml.safe_load`` would leave the zero-config source as a literal
    ``${HOME}/git/src``. ``load_yaml`` raises ``MissingEnvVarError`` /
    ``yaml.YAMLError`` for a missing required var / bad YAML; ``load_config``
    wraps those to :class:`FatalError`, and returns ``{}`` for an empty file.
    """
    resource = Path(__file__).with_name(_DEFAULT_CONFIG_RESOURCE)
    return ConfigurationLoader.load_yaml(resource)


def load_config(config_dir: str | None = None, config_path: str | None = None) -> BackupConfig:
    """Merge the bundled default with user config files and validate.

    Layers, lowest priority first: the bundled ``default.yaml``, then the user
    files returned by :meth:`ConfigurationLoader.find_config_files_ranked`
    (already low-to-high — never reverse it). An explicit ``config_path`` (from
    ``--config FILE``) is the single highest-priority layer, above every
    discovered file. Merged via :meth:`ConfigurationLoader.merge_configs` (later
    wins, ``excludes+`` / ``excludes-`` directives applied), validated against
    :class:`BackupConfig`, and finally checked for unknown capability names /
    inputs.

    Args:
        config_dir: Explicit config directory (from ``--config-dir``), threaded
            from the CLI so the tool plan is discovered under the SAME directory
            the settings were resolved from.
        config_path: Explicit config file (from ``--config``), threaded from the
            CLI so ``backup --config FILE`` runs the plan from FILE rather than
            the default locations.

    Raises:
        FatalError: on malformed YAML in a config file, a merge/directive error,
            a missing required env var, an invalid schema, an unknown capability,
            or an unknown ``with:`` input — every failure the CLI's ``FatalError``
            handler can render, never a raw traceback.
    """
    layers: list[dict[str, object]] = []
    try:
        layers.append(_load_default())
    except (yaml.YAMLError, MissingEnvVarError, OSError, UnicodeError) as exc:
        msg = f"failed to load bundled default configuration: {exc}"
        raise FatalError(msg) from exc
    ranked_files: list[Path] = ConfigurationLoader.find_config_files_ranked(
        "backup", config_dir=config_dir, config_path=config_path
    )
    for path in ranked_files:
        try:
            data = ConfigurationLoader.load_yaml(path)
        except (yaml.YAMLError, MissingEnvVarError, OSError, UnicodeError) as exc:
            msg = f"failed to load config file {path}: {exc}"
            raise FatalError(msg) from exc
        # A backup-SPECIFIC file (buvis-backup*.yaml) should carry only backup's
        # keys, so an unknown top-level key there is a typo (instnaces:, exclude:)
        # to reject — the projection below would otherwise silently drop it and
        # run the bundled plan. A SHARED file (config.yaml / buvis.yaml) legitimately
        # carries other tools' + global keys, so its extras are tolerated.
        if _is_backup_specific(path):
            unknown = _unknown_top_level_keys(data)
            if unknown:
                allowed = ", ".join(sorted(_BACKUP_TOP_LEVEL_KEYS))
                msg = (
                    f"unknown key(s) in {path}: {', '.join(sorted(unknown))}; "
                    f"backup config accepts only: {allowed} (with +/- directive suffixes on list keys)"
                )
                raise FatalError(msg)
        layers.append(data)

    try:
        merged = ConfigurationLoader.merge_configs(*layers, known_keys={"excludes"})
    except (ConfigurationError, yaml.YAMLError, MissingEnvVarError) as exc:
        msg = f"failed to merge backup configuration: {exc}"
        raise FatalError(msg) from exc

    # find_config_files_ranked also returns the SHARED config.yaml / buvis.yaml
    # layers, whose global fields (debug, log_level, ...) are not backup's. Project
    # the merged document onto backup's own top-level keys before validation, so a
    # standard global config no longer trips BackupConfig's extra="forbid". Typos in
    # a backup-SPECIFIC file are already rejected above; a typo nested under
    # instances/excludes is caught by the per-instance extra="forbid" and
    # _validate_capabilities.
    backup_config = {key: value for key, value in merged.items() if key in _BACKUP_TOP_LEVEL_KEYS}

    try:
        cfg = BackupConfig.model_validate(backup_config)
    except ValidationError as exc:
        msg = f"invalid backup configuration: {exc}"
        raise FatalError(msg) from exc

    _validate_capabilities(cfg)
    return cfg


def applicable_instances(cfg: BackupConfig) -> list[tuple[str, BackupInstance]]:
    """Return enabled instances sorted by ``(order, name)``."""
    applicable = [(name, inst) for name, inst in cfg.instances.items() if inst.enabled]
    applicable.sort(key=lambda item: (item[1].order, item[0]))
    return applicable

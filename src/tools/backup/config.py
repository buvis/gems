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


def load_config(config_dir: str | None = None) -> BackupConfig:
    """Merge the bundled default with user config files and validate.

    Layers, lowest priority first: the bundled ``default.yaml``, then the user
    files returned by :meth:`ConfigurationLoader.find_config_files_ranked`
    (already low-to-high — never reverse it). Merged via
    :meth:`ConfigurationLoader.merge_configs` (later wins, ``excludes+`` /
    ``excludes-`` directives applied), validated against :class:`BackupConfig`,
    and finally checked for unknown capability names / inputs.

    Raises:
        FatalError: on malformed YAML in a config file, a merge/directive error,
            a missing required env var, an invalid schema, an unknown capability,
            or an unknown ``with:`` input — every failure the CLI's ``FatalError``
            handler can render, never a raw traceback.
    """
    layers: list[dict[str, object]] = []
    try:
        layers.append(_load_default())
    except (yaml.YAMLError, MissingEnvVarError) as exc:
        msg = f"failed to load bundled default configuration: {exc}"
        raise FatalError(msg) from exc
    ranked_files: list[Path] = ConfigurationLoader.find_config_files_ranked("backup", config_dir=config_dir)
    for path in ranked_files:
        try:
            layers.append(ConfigurationLoader.load_yaml(path))
        except (yaml.YAMLError, MissingEnvVarError) as exc:
            msg = f"failed to load config file {path}: {exc}"
            raise FatalError(msg) from exc

    try:
        merged = ConfigurationLoader.merge_configs(*layers, known_keys={"excludes"})
    except (ConfigurationError, yaml.YAMLError, MissingEnvVarError) as exc:
        msg = f"failed to merge backup configuration: {exc}"
        raise FatalError(msg) from exc

    try:
        cfg = BackupConfig.model_validate(merged)
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

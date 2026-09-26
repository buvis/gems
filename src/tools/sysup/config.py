from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Literal

import yaml
from buvis.pybase.configuration import ConfigurationLoader
from buvis.pybase.result import FatalError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sysup.capabilities import CAPABILITIES

__all__ = [
    "SysupCommand",
    "SysupConfig",
    "WhenSpec",
    "applicable_commands",
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


class SysupCommand(BaseModel):
    """One updater entry: exactly one of ``steps`` (argv sequence) or ``use``
    (named capability + optional ``with:`` inputs)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    order: int = 100
    enabled: bool = True
    when: WhenSpec = WhenSpec()
    interactive: bool = False
    timeout: int | None = None
    continue_on_error: bool = False
    tags: tuple[str, ...] = ()
    steps: tuple[tuple[str, ...], ...] | None = None
    use: str | None = None
    with_: dict[str, object] = Field(default_factory=dict, alias="with")

    @model_validator(mode="after")
    def _exactly_one_kind(self: SysupCommand) -> SysupCommand:
        if bool(self.steps) == bool(self.use):
            msg = "entry must have exactly one of `steps` or `use`"
            raise ValueError(msg)
        return self


class SysupConfig(BaseModel):
    """The whole merged, validated sysup configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commands: dict[str, SysupCommand] = {}
    prime: tuple[str, ...] = ()


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


def load_config(config_dir: str | None = None) -> SysupConfig:
    """Merge the bundled default with user config files and validate.

    Layers, lowest priority first: the bundled ``default.yaml``, then the user
    files returned by :meth:`ConfigurationLoader.find_config_files_ranked`
    (already low-to-high — never reverse it). Merged via
    :meth:`ConfigurationLoader.merge_configs` (later wins), validated against
    :class:`SysupConfig`, and finally checked for unknown capability names /
    inputs against the registry.

    Raises:
        FatalError: on invalid YAML schema, an unknown capability, or an unknown
            ``with:`` input.
    """
    layers: list[dict[str, object]] = [_load_default()]
    ranked_files: list[Path] = ConfigurationLoader.find_config_files_ranked("sysup", config_dir=config_dir)
    for path in ranked_files:
        layers.append(ConfigurationLoader.load_yaml(path))

    merged = ConfigurationLoader.merge_configs(*layers)

    try:
        cfg = SysupConfig.model_validate(merged)
    except ValidationError as exc:
        msg = f"invalid sysup configuration: {exc}"
        raise FatalError(msg) from exc

    _validate_capabilities(cfg)
    return cfg


def applicable_commands(cfg: SysupConfig) -> list[tuple[str, SysupCommand]]:
    """Return enabled entries whose ``when`` matches this host, sorted by
    ``(order, name)``.

    An entry is applicable when it is ``enabled``, its ``when.os`` (if set)
    equals :data:`sys.platform`, and its ``when.check`` binary (if set) resolves
    via :func:`shutil.which`.
    """
    applicable: list[tuple[str, SysupCommand]] = []
    for name, command in cfg.commands.items():
        if not command.enabled:
            continue
        if command.when.os is not None and command.when.os != sys.platform:
            continue
        if command.when.check is not None and shutil.which(command.when.check) is None:
            continue
        applicable.append((name, command))

    applicable.sort(key=lambda item: (item[1].order, item[0]))
    return applicable

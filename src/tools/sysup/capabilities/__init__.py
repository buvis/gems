from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sysup.capabilities.gh_token import GhTokenExpiry
from sysup.capabilities.helm import HelmRepoUpdate
from sysup.capabilities.nvim_mason import NvimMason
from sysup.capabilities.pip import PipOutdated
from sysup.capabilities.pipx_python import PipxPython
from sysup.capabilities.sudo import SudoPrime
from sysup.capabilities.uv_tool_python import UvToolPython
from sysup.capabilities.x509 import X509Expiry

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from datetime import datetime

    from sysup.step_result import StepResult

__all__ = [
    "CAPABILITIES",
    "EXPIRY_CAPABILITIES",
    "Capability",
    "ExpiryCapability",
    "GhTokenExpiry",
    "X509Expiry",
]


@runtime_checkable
class Capability(Protocol):
    """A built-in, code-owned updater referenced from config by name.

    ``inputs`` declares the accepted ``with:`` keys mapped to their default
    values, so ``load_config`` can reject unknown inputs. ``run`` executes the
    capability and yields one :class:`StepResult` per reported step. A capability
    may raise :class:`buvis.pybase.result.FatalError` for an unrecoverable
    precondition (e.g. a missing required binary); any other exception is caught
    by the runner and turned into a failed step.
    """

    @property
    def inputs(self: Capability) -> Mapping[str, object]: ...

    def run(self: Capability, **kwargs: object) -> Iterator[StepResult]: ...


CAPABILITIES: dict[str, Capability] = {
    "helm-repo-update": HelmRepoUpdate(),
    "nvim-mason": NvimMason(),
    "pip-outdated": PipOutdated(),
    "pipx-python": PipxPython(),
    "sudo-prime": SudoPrime(),
    "uv-tool-python": UvToolPython(),
}


@runtime_checkable
class ExpiryCapability(Protocol):
    """A built-in, code-owned expiry probe referenced from config by name.

    ``inputs`` declares the accepted ``with:`` keys mapped to their default
    values, so ``load_config`` can reject unknown inputs; a default of ``None``
    marks a key the config validator treats as required on an enabled item.
    ``expires_at`` returns an aware :class:`datetime.datetime` when the expiry is
    known, or a :class:`str` naming why it is unknown. A probe may raise
    :class:`buvis.pybase.result.FatalError` for an unrecoverable precondition;
    any other exception is caught by the runner and reported as unknown.
    """

    @property
    def inputs(self: ExpiryCapability) -> Mapping[str, object]: ...

    def expires_at(self: ExpiryCapability, **kwargs: object) -> datetime | str: ...


EXPIRY_CAPABILITIES: dict[str, ExpiryCapability] = {
    "gh-token-expiry": GhTokenExpiry(),
    "x509-expiry": X509Expiry(),
}

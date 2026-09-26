from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sysup.capabilities.helm import HelmRepoUpdate
from sysup.capabilities.nvim_mason import NvimMason
from sysup.capabilities.pip import PipOutdated
from sysup.capabilities.sudo import SudoPrime

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from sysup.step_result import StepResult

__all__ = ["CAPABILITIES", "Capability"]


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
    "sudo-prime": SudoPrime(),
}

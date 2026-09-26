from __future__ import annotations

import shutil
import subprocess
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from sysup.step_result import StepResult

__all__ = ["SudoPrime"]


class SudoPrime:
    """Session capability: cache sudo credentials up front with a background
    refresher, released via the returned stop callback.

    Referenced from ``prime:`` rather than a ``use:`` entry — the runner calls
    :meth:`prime` before any command and invokes the returned stop callback in
    a ``finally`` around the whole run.
    """

    @property
    def inputs(self: SudoPrime) -> Mapping[str, object]:
        return {}

    def run(self: SudoPrime, **kwargs: object) -> Iterator[StepResult]:  # noqa: ARG002
        """Not used as a ``use:`` entry; priming is driven via :meth:`prime`."""
        return iter(())

    def prime(self: SudoPrime) -> Callable[[], None]:
        """Cache sudo credentials upfront so brew casks don't prompt mid-run.

        Returns a stop callback for the background refresher that keeps the
        ticket fresh past sudo's 5-minute timeout. A missing sudo or a declined
        prompt is not an error: later steps then prompt as before.
        """
        sudo_path = shutil.which("sudo")
        if sudo_path is None:
            return lambda: None
        prime = subprocess.run([sudo_path, "-v"], check=False)
        if prime.returncode != 0:
            return lambda: None

        stop = threading.Event()

        def refresh() -> None:
            while not stop.wait(60):
                subprocess.run([sudo_path, "-n", "-v"], capture_output=True, check=False)

        threading.Thread(target=refresh, daemon=True).start()
        return stop.set

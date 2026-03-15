from __future__ import annotations

import time

from buvis.pybase.result import CommandResult
from ping3 import ping


class CommandWait:
    def __init__(self: CommandWait, host: str, timeout: int) -> None:
        self.host = host
        self.timeout = timeout

    def execute(self: CommandWait) -> CommandResult:
        start_time = time.time()
        while True:
            response = ping(self.host, timeout=1)
            if response:
                return CommandResult(success=True)
            if time.time() - start_time > self.timeout:
                return CommandResult(
                    success=False,
                    error=f"Timeout reached when waiting for {self.host}",
                )
            time.sleep(1)

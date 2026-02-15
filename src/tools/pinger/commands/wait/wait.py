import time

from ping3 import ping
from pinger.commands.wait.exceptions import CommandWaitTimeoutError


class CommandWait:
    def __init__(self: "CommandWait", host: str, timeout: int) -> None:
        self.host = host
        self.timeout = timeout

    def execute(self: "CommandWait") -> None:
        start_time = time.time()
        while True:
            response = ping(self.host, timeout=1)
            if response:
                break
            if time.time() - start_time > self.timeout:
                raise CommandWaitTimeoutError
            time.sleep(1)

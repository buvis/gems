from __future__ import annotations

from buvis.pybase.result import CommandResult

from readerctl.adapters import ReaderAPIAdapter


class CommandAdd:
    def __init__(self: CommandAdd, token: str) -> None:
        self.api = ReaderAPIAdapter(token)

    def execute(self: CommandAdd, url: str) -> CommandResult:
        res = self.api.add_url(url)

        if res.is_ok():
            return CommandResult(success=True, output=res.message)
        return CommandResult(success=False, error=res.message)

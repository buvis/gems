from __future__ import annotations

import getpass
from pathlib import Path

from buvis.pybase.result import CommandResult, FatalError

from readerctl.adapters import ReaderAPIAdapter


class CommandLogin:
    def __init__(self, token_file: Path) -> None:
        self.token_file = token_file

    def execute(self) -> CommandResult:
        try:
            token = self.token_file.read_text().strip()
        except FileNotFoundError:
            token = ""

        if token:
            token_check = ReaderAPIAdapter.check_token(token)

            if token_check.is_ok():
                return CommandResult(success=True, output="API token valid", metadata={"token": token})
            raise FatalError(f"Token check failed: {token_check.code} - {token_check.message}")
        else:
            token = getpass.getpass("Enter Readwise API token: ")
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(token)
            token_check = ReaderAPIAdapter.check_token(token)

            if token_check.is_ok():
                return CommandResult(success=True, output="API token stored for future use", metadata={"token": token})
            raise FatalError(f"Token check failed: {token_check.code} - {token_check.message}")

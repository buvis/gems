from pathlib import Path

from buvis.pybase.adapters import console

from readerctl.adapters import ReaderAPIAdapter


class CommandLogin:
    def __init__(self, token_file: Path) -> None:
        self.token_file = token_file

    def execute(self) -> str | None:
        try:
            token = self.token_file.read_text().strip()
        except FileNotFoundError:
            token = ""

        if token:
            token_check = ReaderAPIAdapter.check_token(token)

            if token_check.is_ok():
                console.success("API token valid")
                return token
            else:
                console.panic(
                    f"Token check failed: {token_check.code} - {token_check.message}",
                )
                return None
        else:
            token = str(console.input_password("Enter Readwise API token: "))
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(token)
            token_check = ReaderAPIAdapter.check_token(token)

            if token_check.is_ok():
                console.success("API token stored for future use")
                return token
            else:
                console.panic(
                    f"Token check failed: {token_check.code} - {token_check.message}",
                )
                return None

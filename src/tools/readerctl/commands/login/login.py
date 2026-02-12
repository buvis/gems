from pathlib import Path

from buvis.pybase.adapters import console

from readerctl.adapters import ReaderAPIAdapter

TOKEN_FILE = Path.home() / ".config" / "scripts" / "readwise-token"


class CommandLogin:
    def __init__(self: "CommandLogin") -> None:
        pass

    def execute(self: "CommandLogin") -> str | None:
        try:
            token = TOKEN_FILE.read_text().strip()
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
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(token)
            token_check = ReaderAPIAdapter.check_token(token)

            if token_check.is_ok():
                console.success("API token stored for future use")
                return token
            else:
                console.panic(
                    f"Token check failed: {token_check.code} - {token_check.message}",
                )
                return None

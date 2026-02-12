from buvis.pybase.adapters import console

from readerctl.adapters import ReaderAPIAdapter


class CommandAdd:
    def __init__(self: "CommandAdd", token: str) -> None:
        self.api = ReaderAPIAdapter(token)

    def execute(self: "CommandAdd", url: str) -> None:
        res = self.api.add_url(url)

        if res.is_ok():
            console.success(res.message)
        else:
            console.failure(res.message)

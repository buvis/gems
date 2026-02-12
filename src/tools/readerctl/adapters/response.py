class AdapterResponse:
    def __init__(self, code: int = 0, message: str = "") -> None:
        self.code = code
        self.message = message

    def is_ok(self) -> bool:
        return self.code == 0

    def is_nok(self) -> bool:
        return self.code != 0

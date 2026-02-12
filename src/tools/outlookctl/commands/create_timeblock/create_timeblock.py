import os

from buvis.pybase.adapters import console


class CommandCreateTimeblock:
    def __init__(self, duration: int) -> None:
        self.duration = duration
        self.outlook = None

        if os.name != "nt":
            console.warning("OutlookLocalAdapter only available on Windows")
            return

        try:
            from buvis.pybase.adapters import OutlookLocalAdapter

            self.outlook = OutlookLocalAdapter()
        except Exception as e:
            console.panic(e)

    def execute(self) -> None:
        console.print(f"Would create a timeblock of {self.duration} minutes", mode="raw")

from __future__ import annotations


class StepResult:
    def __init__(self: StepResult, label: str, success: bool, message: str = "") -> None:
        self.label = label
        self.success = success
        self.message = message

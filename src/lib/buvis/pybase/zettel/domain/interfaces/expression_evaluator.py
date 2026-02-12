from __future__ import annotations

from typing import Any, Protocol


class ExpressionEvaluator(Protocol):
    def __call__(self, expression: str, context: dict[str, Any]) -> Any: ...

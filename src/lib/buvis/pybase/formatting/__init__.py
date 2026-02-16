"""String formatting utilities for BUVIS Python projects.

StringOperator provides a unified interface for slugification, case conversion,
abbreviation expansion, and word operations.

Example:
    from buvis.pybase.formatting import StringOperator
    StringOperator.slugify("Hello World!")  # returns "hello-world"
"""

from __future__ import annotations

from .string_operator.string_operator import StringOperator

__all__ = ["StringOperator"]

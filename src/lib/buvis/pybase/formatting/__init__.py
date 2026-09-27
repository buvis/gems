"""String formatting utilities for BUVIS Python projects.

StringOperator provides a unified interface for case conversion, abbreviation
expansion, and note-field naming.

Example:
    from buvis.pybase.formatting import StringOperator
    StringOperator.camelize("first_name")  # returns "FirstName"
"""

from __future__ import annotations

from .string_operator.string_operator import StringOperator

__all__ = ["StringOperator"]

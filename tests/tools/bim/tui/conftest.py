from __future__ import annotations

from textual.widgets import Select

# Bridge Select.NULL → Select.BLANK for codebases written against older Textual API
if not hasattr(Select, "NULL"):
    Select.NULL = Select.BLANK  # type: ignore[attr-defined]

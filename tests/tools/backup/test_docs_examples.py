"""The YAML examples in docs/source/tools/backup.rst must be usable configs."""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest
import yaml

_DOC = Path(__file__).resolve().parents[3] / "docs" / "source" / "tools" / "backup.rst"
_BLOCKS = re.findall(r"\.\. code-block:: yaml\n\n((?:    .*\n|\n)+)", _DOC.read_text(encoding="utf-8"))


@pytest.mark.parametrize("block", _BLOCKS, ids=range(len(_BLOCKS)))
def test_instance_examples_keep_string_source_and_out(block: str) -> None:
    """A bare ``~`` is YAML null, so ``source: ~`` silently configures no source."""
    data = yaml.safe_load(textwrap.dedent(block)) or {}
    for name, instance in (data.get("instances") or {}).items():
        for key in ("source", "out"):
            if key in instance.get("with", {}):
                value = instance["with"][key]
                assert isinstance(value, str) and value, f"{name}: {key} is {value!r}, not a path string"

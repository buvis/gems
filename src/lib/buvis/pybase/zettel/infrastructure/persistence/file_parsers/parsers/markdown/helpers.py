from __future__ import annotations

import re
from typing import Any, cast

import yaml
from buvis.pybase.formatting import StringOperator

from .back_matter_preprocessor import (
    ZettelParserMarkdownBackMatterPreprocessor as BMPreprocessor,
)
from .front_matter_preprocessor import (
    ZettelParserMarkdownFrontMatterPreprocessor as FMPreprocessor,
)


class _ZettelSafeLoader(yaml.SafeLoader):
    """SafeLoader without YAML 1.1 sexagesimal int resolver.

    PyYAML parses ``11:30`` as int 690 (base-60). We replace the int
    resolver regex with one that drops the sexagesimal alternative,
    keeping time-like strings as strings to match Rust serde_yml.
    """


# PyYAML's int resolver uses one regex covering binary, octal, decimal, hex,
# AND sexagesimal. We rebuild without the sexagesimal alternative
# (^[1-9][0-9_]*(?::[0-5]?[0-9])+$).
_INT_NO_SEXA = re.compile(
    r"^[-+]?0b[0-1_]+$"
    r"|^[-+]?0[0-7_]+$"
    r"|^[-+]?(?:0|[1-9][0-9_]*)$"
    r"|^[-+]?0x[0-9a-fA-F_]+$",
)

# Deep-copy the parent's resolvers to avoid mutating yaml.SafeLoader,
# and swap the int pattern
_ZettelSafeLoader.yaml_implicit_resolvers = {
    k: [(tag, _INT_NO_SEXA if tag == "tag:yaml.org,2002:int" else regexp) for tag, regexp in v]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

METADATA_SECTION_REGEX = r"---\n(.*?)\n---"
REFERENCE_SECTION_REGEX = r"\n---\n(.*)$"
HEADING_REGEX = r"(#{1,6} .+?)\n"


def extract_metadata(content: str) -> tuple[dict[str, Any] | None, str]:
    match = re.search(METADATA_SECTION_REGEX, content, re.DOTALL)

    if not match:
        return None, content

    front_matter = FMPreprocessor.preprocess(match.group(1))

    try:
        metadata = cast(
            dict[str, Any],
            yaml.load(front_matter, Loader=_ZettelSafeLoader) or {},  # noqa: S506
        )
    except yaml.YAMLError as e:
        msg = f"Failed to parse metadata: {e}"
        raise ValueError(msg) from e

    content_without_front_matter = content.replace(match.group(0), "", 1)

    return metadata, content_without_front_matter


def extract_reference(content: str) -> tuple[dict[str, Any] | None, str]:
    match = re.search(REFERENCE_SECTION_REGEX, content, re.DOTALL)

    if not match:
        return None, content

    raw_reference_content = match.group(1).strip()
    preprocessed_reference_content = BMPreprocessor.preprocess(raw_reference_content)

    try:
        reference_raw = cast(
            list[dict[str, Any]],
            yaml.load(
                preprocessed_reference_content,
                Loader=_ZettelSafeLoader,  # noqa: S506
            )
            or [],
        )
        reference: dict[str, Any] = {}

        for item in reference_raw:
            for key, value in item.items():
                key = key.rstrip(":")

                if key not in reference:
                    reference[key] = value
                else:
                    existing = reference[key]

                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        reference[key] = [existing, value]
    except yaml.YAMLError as e:
        msg = f"Failed to parse reference: {e}"
        raise ValueError(msg) from e

    content_without_reference = re.sub(
        r"(^---$)[\s\S]*",
        "",
        content,
        flags=re.MULTILINE,
    )
    content_without_reference = content_without_reference.rstrip()

    return reference, content_without_reference


def normalize_dict_keys(data: dict[str, Any]) -> dict[str, Any]:
    return {StringOperator.as_note_field_name(key): value for key, value in data.items()}


def split_content_into_sections(content: str) -> list[tuple[str, str]]:
    sections = re.split(HEADING_REGEX, content)[1:]  # Skip the first empty element

    if not sections:
        return [("", content)]

    return [(sections[i], sections[i + 1]) for i in range(0, len(sections), 2)]

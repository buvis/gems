from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

from .helpers import (
    extract_metadata,
    extract_reference,
    normalize_dict_keys,
    split_content_into_sections,
)


class MarkdownZettelFileParser:
    @staticmethod
    def parse(content: str) -> ZettelData:
        zettel_raw_data = ZettelData()

        metadata, content = extract_metadata(content)
        zettel_raw_data.metadata = normalize_dict_keys(metadata) if metadata else {}

        reference, content = extract_reference(
            content,
        )

        zettel_raw_data.reference = normalize_dict_keys(reference) if reference else {}

        zettel_raw_data.sections = split_content_into_sections(
            content,
        )

        return zettel_raw_data

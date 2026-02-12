from datetime import datetime

import pytest
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.helpers import (
    convert_datetimes,
    format_metadata,
    metadata_to_yaml,
    process_metadata,
)


# Fixture for common metadata
@pytest.fixture
def sample_metadata() -> dict:
    return {
        "name": "John Doe",
        "date": datetime.now(),
        "email": "john.doe@example.com",
        "age": 30,
    }


# Test processing metadata with prioritized keys
def test_process_metadata(sample_metadata: dict):
    first_keys = ("name", "email")
    processed = process_metadata(sample_metadata, first_keys)
    # Check if first keys are indeed first in the returned dictionary
    first_in_result = list(processed.keys())[: len(first_keys)]
    assert first_in_result == list(first_keys), "First keys are not prioritized in the result"


# Test converting datetime objects to strings
def test_convert_datetimes(sample_metadata: dict):
    keys_converted = convert_datetimes(sample_metadata)
    # Check if the date key was converted
    assert "date" in keys_converted, "Datetime was not converted"
    assert isinstance(sample_metadata["date"], str), "Datetime not converted to string"


# Test the YAML conversion maintains the correct format and removes quotes
def test_metadata_to_yaml(sample_metadata: dict):
    datetime_keys = convert_datetimes(sample_metadata)
    assert "date" in datetime_keys
    yaml_str = metadata_to_yaml(sample_metadata, datetime_keys)
    # Check if datetime is not quoted
    assert "'" not in yaml_str, "Datetime values should not be quoted in YAML"


# Test the overall formatting function
def test_format_metadata(sample_metadata: dict):
    first_keys = ("name", "email")
    formatted_yaml = format_metadata(sample_metadata, first_keys)
    # Basic checks to ensure it returns a string and contains key data
    assert isinstance(formatted_yaml, str), "Formatted metadata should be a string"
    assert "John Doe" in formatted_yaml, "Metadata content missing in the formatted output"

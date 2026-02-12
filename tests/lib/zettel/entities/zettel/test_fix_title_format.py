from unittest.mock import patch

import pytest
from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.fix_title_format import (
    fix_title_format,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def sample_zettel_data():
    zettel_data = ZettelData()
    zettel_data.metadata = {"title": "PhD. John Doe"}
    return zettel_data


def test_fix_title_format(sample_zettel_data):
    # Mock the replace_abbreviations method to return a specific value
    with patch.object(StringOperator, "replace_abbreviations", return_value="Doctor John Doe") as mock_method:
        fix_title_format(sample_zettel_data)
        mock_method.assert_called_once_with(text="PhD. John Doe", level=0)
        assert sample_zettel_data.metadata["title"] == "Doctor John Doe", (
            "The title should be formatted to 'Doctor John Doe'"
        )


def test_fix_title_format_idempotence(sample_zettel_data):
    # Test to ensure that running the function twice does not change the outcome after the first modification
    with patch.object(StringOperator, "replace_abbreviations", return_value="Doctor John Doe") as mock_method:
        fix_title_format(sample_zettel_data)  # First call to modify the title
        assert sample_zettel_data.metadata["title"] == "Doctor John Doe", (
            "The title should be formatted to 'Doctor John Doe'"
        )
        fix_title_format(sample_zettel_data)  # Second call with the already modified title
        mock_method.assert_called_with(text="Doctor John Doe", level=0)
        assert sample_zettel_data.metadata["title"] == "Doctor John Doe", (
            "The title should remain 'Doctor John Doe' after the second call"
        )

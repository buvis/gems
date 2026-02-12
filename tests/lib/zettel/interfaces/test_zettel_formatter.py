from unittest.mock import create_autospec

from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class ConcreteZettelFormatter(ZettelFormatter):
    @staticmethod
    def format(zettel_data: "ZettelData") -> str:
        return "Formatted Data"


def test_zettel_formatter():
    zettel_data = create_autospec(ZettelData)
    formatter = ConcreteZettelFormatter()
    assert formatter.format(zettel_data) == "Formatted Data"

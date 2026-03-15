"""Shared fixer/upgrade runner infrastructure for zettel entities."""

from __future__ import annotations

from collections.abc import Callable

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

Fixer = Callable[[ZettelData], None]


def apply_fixers(zettel_data: ZettelData, fixers: list[Fixer]) -> None:
    """Run fixers in order, modifying zettel_data in place."""
    for fixer in fixers:
        fixer(zettel_data)


def apply_defaults(
    zettel_data: ZettelData,
    defaults: dict[str, Fixer],
) -> None:
    """Apply fixers only when the corresponding metadata key is None."""
    for key, fixer in defaults.items():
        if zettel_data.metadata.get(key, None) is None:
            fixer(zettel_data)

"""
Zettel module.

This module contains the Zettel class which represents a Zettel entity.

Imports:
    - :class:`datetime.datetime`: Used for type hinting.
    - :class:`ZettelConsistencyService`: Service for ensuring Zettel consistency.
    - :class:`ZettelMigrationService`: Service for migrating Zettel data.
    - :class:`ZettelData`: Value object representing Zettel data.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.zettel_consistency_service import (
    ZettelConsistencyService,
)
from buvis.pybase.zettel.domain.entities.zettel.services.migration.zettel_migration_service import (
    ZettelMigrationService,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class Zettel:
    """
    Zettel class representing a Zettel entity.

    :param zettel_data: Optional :class:`ZettelData` object to initialize the Zettel.
    :type zettel_data: :class:`ZettelData` or None
    """

    def __init__(self, zettel_data: ZettelData | None = None, *, from_rust: bool = False) -> None:
        """Initialize a new Zettel instance."""
        self._data = ZettelData()
        self._from_rust = from_rust

        if zettel_data:
            if from_rust:
                self._data = zettel_data
                self._alias_attributes()
            else:
                self.replace_data(zettel_data)

    def get_data(self) -> ZettelData:
        """
        Get the Zettel data.

        :return: The :class:`ZettelData` object.
        :rtype: :class:`ZettelData`
        """
        return self._data

    def replace_data(self, zettel_data: ZettelData) -> None:
        """
        Replace the Zettel data.

        :param zettel_data: The new :class:`ZettelData` object.
        :type zettel_data: :class:`ZettelData`
        :return: None. The function modifies the Zettel data in place.
        """
        self._data = zettel_data
        self._ensure_consistency()
        self._migrate()
        self._ensure_consistency()
        self._alias_attributes()

    @property
    def data(self) -> ZettelData:
        """Return the Zettel data."""
        return self._data

    @property
    def from_rust(self) -> bool:
        """Return whether the Zettel was created from Rust data."""
        return self._from_rust

    def _migrate(self) -> None:
        """Migrate the Zettel data."""
        ZettelMigrationService.migrate(self._data)

    def _ensure_consistency(self) -> None:
        """Ensure the consistency of the Zettel data."""
        ZettelConsistencyService.ensure_consistency(self._data)

    def _alias_attributes(self) -> None:
        """Alias the Zettel attributes.

        When from_rust=True, skips keys with property descriptors to avoid
        triggering setters that run migration/consistency (Rust already did it).
        """
        cls = type(self)
        for key, value in {**self._data.metadata, **self._data.reference}.items():
            attr = key.replace("-", "_")
            if self._from_rust and isinstance(getattr(cls, attr, None), property):
                continue
            setattr(self, attr, value)

    @property
    def id(self) -> int | None:
        """
        Get the Zettel ID.

        :return: The Zettel ID.
        :rtype: int or None
        """
        if self._data.metadata.get("id") is None:
            return None
        try:
            return int(self._data.metadata["id"])
        except ValueError:
            return None

    @id.setter
    def id(self, value: int) -> None:
        """
        Set the Zettel ID.

        :param value: The new Zettel ID.
        :type value: int
        :raises ValueError: If the provided value is not a valid integer.
        """
        try:
            self._data.metadata["id"] = int(value)
        except ValueError as err:
            raise ValueError from err
        except TypeError as err:
            raise TypeError from err
        self._migrate()
        self._ensure_consistency()

    @property
    def title(self) -> str | None:
        """
        Get the Zettel title.

        :return: The Zettel title.
        :rtype: str or None
        """
        if self._data.metadata.get("title") is None:
            return None
        return str(self._data.metadata["title"])

    @title.setter
    def title(self, value: str) -> None:
        """
        Set the Zettel title.

        :param value: The new Zettel title.
        :type value: str
        """
        if value is None:
            self._data.metadata["title"] = None
        else:
            self._data.metadata["title"] = str(value)
        self._migrate()
        self._ensure_consistency()

    @property
    def date(self) -> datetime | None:
        """
        Get the Zettel date.

        :return: The Zettel date.
        :rtype: :class:`datetime.datetime` or None
        """
        if self._data.metadata.get("date") is None:
            return None
        return cast(datetime, self._data.metadata["date"])

    @date.setter
    def date(self, value: datetime) -> None:
        """
        Set the Zettel date.

        :param value: The new Zettel date.
        :type value: :class:`datetime.datetime`
        """
        self._data.metadata["date"] = value
        self._migrate()
        self._ensure_consistency()

    @property
    def type(self) -> str | None:
        """
        Get the Zettel type.

        :return: The Zettel type.
        :rtype: str or None
        """
        if self._data.metadata.get("type") is None:
            return None
        return str(self._data.metadata["type"])

    @type.setter
    def type(self, value: str) -> None:
        """
        Set the Zettel type.

        :param value: The new Zettel type.
        :type value: str
        """
        if value is None:
            self._data.metadata["type"] = None
        else:
            self._data.metadata["type"] = str(value)
        self._migrate()
        self._ensure_consistency()

    @property
    def tags(self) -> list[str] | None:
        """
        Get the Zettel tags.

        :return: The Zettel tags.
        :rtype: list[str] or None
        """
        if self._data.metadata.get("tags") is None:
            return None
        return cast(list[str], self._data.metadata["tags"])

    @tags.setter
    def tags(self, value: list[str] | str) -> None:
        """
        Set the Zettel tags.

        :param value: The new Zettel tags.
        :type value: list[str] or str
        """
        if value and not isinstance(value, list):
            value = [value]
        self._data.metadata["tags"] = value
        self._migrate()
        self._ensure_consistency()

    @property
    def publish(self) -> bool:
        """
        Get the Zettel publish status.

        :return: The Zettel publish status.
        :rtype: bool
        """
        if self._data.metadata.get("publish") is None:
            return False
        return cast(bool, self._data.metadata["publish"])

    @publish.setter
    def publish(self, value: bool) -> None:
        """
        Set the Zettel publish status.

        :param value: The new Zettel publish status.
        :type value: bool
        """
        self._data.metadata["publish"] = bool(value)
        self._migrate()
        self._ensure_consistency()

    @property
    def processed(self) -> bool:
        """
        Get the Zettel processed status.

        :return: The Zettel processed status.
        :rtype: bool
        """
        if self._data.metadata.get("processed") is None:
            return False
        return cast(bool, self._data.metadata["processed"])

    @processed.setter
    def processed(self, value: bool) -> None:
        """
        Set the Zettel processed status.

        :param value: The new Zettel processed status.
        :type value: bool
        """
        self._data.metadata["processed"] = bool(value)
        self._migrate()
        self._ensure_consistency()

from __future__ import annotations

from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
)


def get_repo(*, extensions: list[str] | None = None) -> ZettelRepository:
    return MarkdownZettelRepository(extensions=extensions)

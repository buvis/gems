from __future__ import annotations

from buvis.pybase.zettel.domain.templates.contact import ContactTemplate


class TestContactTemplate:
    def test_is_placed_under_contact_by_slug_and_tagged_person(self) -> None:
        t = ContactTemplate()
        assert t.name == "contact"
        assert t.folder == "contact"
        assert t.file_stem == "slug"
        assert t.default_tags == ["person"]
        assert t.hooks() == []

    def test_questions_are_optional_with_empty_defaults(self) -> None:
        qs = ContactTemplate().questions()
        assert [q.key for q in qs] == ["company", "job-title", "email"]
        assert all(q.default == "" and q.required is False for q in qs)

    def test_capitalizes_every_word_and_names_photo_by_slug(self) -> None:
        data = ContactTemplate().build_data({"title": "ada lovelace", "tags": "person", "email": "ada@example.com"})

        assert data.metadata["title"] == "Ada Lovelace"
        assert data.metadata["type"] == "contact"
        assert data.metadata["contact-type"] == "person"
        assert data.metadata["summary"] == ""
        assert data.metadata["company"] == ""
        assert data.metadata["job-title"] == ""
        assert data.metadata["email"] == "ada@example.com"
        assert data.metadata["tags"] == ["person"]
        assert data.sections == [
            ("# Ada Lovelace", "![Ada Lovelace photo|180](ada-lovelace.jpeg)"),
            ("## First contact", ""),
            ("## Timeline", ""),
            ("## Relationships", ""),
        ]
        assert data.reference == {}

    def test_keeps_inner_casing_of_names(self) -> None:
        data = ContactTemplate().build_data({"title": "ronald mcDonald"})
        assert data.metadata["title"] == "Ronald McDonald"

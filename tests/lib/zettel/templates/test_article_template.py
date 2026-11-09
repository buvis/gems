from __future__ import annotations

from buvis.pybase.zettel.domain.templates.article import ArticleTemplate


class TestArticleTemplate:
    def test_article_template_is_a_note_with_backmatter(self) -> None:
        t = ArticleTemplate()
        assert t.name == "article"
        assert [(q.key, q.required) for q in t.questions()] == [("web", False)]
        assert t.hooks() == []

        data = t.build_data(
            {"title": "T", "archive_link": "[T](file:///a/T.md)", "web": "https://example.com", "tags": "x"}
        )

        assert data.metadata["type"] == "note"
        assert data.metadata["title"] == "T"
        assert data.metadata["tags"] == ["x"]
        assert data.sections == [("# T", "")]
        assert data.reference == {"article": "[T](file:///a/T.md)", "web": "[T](https://example.com)"}

    def test_without_web_only_the_archive_link_is_written(self) -> None:
        data = ArticleTemplate().build_data({"title": "T", "archive_link": "[T](file:///a/T.md)", "web": " "})
        assert data.reference == {"article": "[T](file:///a/T.md)"}

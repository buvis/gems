from __future__ import annotations

from unittest.mock import call

from buvis.pybase.formatting.string_operator.tag_suggester import (
    KeywordExtractor,
    NLTKPreprocessor,
    TagSuggester,
)


def test_download_nltk_dependencies_invokes_all_packages(mocker) -> None:
    mock_download = mocker.patch("buvis.pybase.formatting.string_operator.tag_suggester.nltk.download")

    NLTKPreprocessor.download_nltk_dependencies()

    expected_dependencies = [
        "punkt",
        "averaged_perceptron_tagger",
        "averaged_perceptron_tagger_eng",
        "stopwords",
        "wordnet",
        "omw-1.4",
        "punkt_tab",
    ]
    assert mock_download.call_args_list == [call(dependency, quiet=True) for dependency in expected_dependencies]


def test_extract_by_frequency_filters_non_nouns(mocker) -> None:
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.word_tokenize",
        return_value=["python", "python", "is", "awesome", "."],
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.stopwords.words",
        return_value=["is"],
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.pos_tag",
        return_value=[
            ("python", "NN"),
            ("python", "NN"),
            ("awesome", "JJ"),
            (".", "."),
        ],
    )

    extractor = KeywordExtractor()
    assert extractor.extract_by_frequency("text") == ["python"]


def test_extract_by_rake_lemmatizes_and_filters_keywords(mocker) -> None:
    class DummyRake:
        def __init__(self) -> None:
            self.input_text = ""

        def extract_keywords_from_text(self, text: str) -> None:
            self.input_text = text

        def get_ranked_phrases(self) -> list[str]:
            return ["Best Keyword", "Keyword", "Short", "a"]

    class DummyLemmatizer:
        def lemmatize(self, word: str) -> str:
            return word

    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.Rake",
        return_value=DummyRake(),
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.WordNetLemmatizer",
        return_value=DummyLemmatizer(),
    )

    extractor = KeywordExtractor()
    keywords = extractor.extract_by_rake("text")

    assert set(keywords) == {"best keyword", "short"}
    assert len(keywords) == 2


def test_tag_suggester_sets_device_to_mps_when_available(mocker) -> None:
    mock_pipeline = mocker.Mock()
    pipeline = mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.pipeline",
        return_value=mock_pipeline,
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.torch.backends.mps.is_available",
        return_value=True,
    )

    suggester = TagSuggester()

    assert suggester.device == "mps"
    assert suggester.classifier is mock_pipeline
    pipeline.assert_called_once_with(
        "zero-shot-classification",
        model="facebook/bart-large-mnli",
        device="mps",
    )


def test_get_used_tags_handles_missing_file(tmp_path, mocker) -> None:
    mock_pipeline = mocker.Mock()
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.pipeline",
        return_value=mock_pipeline,
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.torch.backends.mps.is_available",
        return_value=False,
    )

    suggester = TagSuggester()
    suggester.used_tags_path = tmp_path / "candidate_tags"

    assert suggester._get_used_tags() == []


def test_get_used_tags_reads_existing_file(tmp_path, mocker) -> None:
    mock_pipeline = mocker.Mock()
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.pipeline",
        return_value=mock_pipeline,
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.torch.backends.mps.is_available",
        return_value=False,
    )

    candidate_file = tmp_path / "candidate_tags"
    candidate_file.write_text("tag-one\nanother-tag")

    suggester = TagSuggester()
    suggester.used_tags_path = candidate_file

    assert suggester._get_used_tags() == ["tag-one", "another-tag"]


def test_classify_candidates_returns_label_score_pairs(mocker) -> None:
    classifier = mocker.Mock(return_value={"labels": ["tag"], "scores": [0.9]})
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.pipeline",
        return_value=classifier,
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.torch.backends.mps.is_available",
        return_value=False,
    )

    suggester = TagSuggester()
    result = suggester._classify_candidates("text", ["tag"])

    assert result == [("tag", 0.9)]
    classifier.assert_called_once_with(
        "text",
        candidate_labels=["tag"],
        multi_label=True,
    )


def test_suggest_prioritizes_used_tags(mocker) -> None:
    mock_pipeline = mocker.Mock()
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.pipeline",
        return_value=mock_pipeline,
    )
    mocker.patch(
        "buvis.pybase.formatting.string_operator.tag_suggester.torch.backends.mps.is_available",
        return_value=False,
    )
    mocker.patch("buvis.pybase.formatting.string_operator.tag_suggester.NLTKPreprocessor.download_nltk_dependencies")

    suggester = TagSuggester()
    mocker.patch.object(
        TagSuggester,
        "_get_used_tags",
        return_value=["tag-one"],
    )

    def classify(_text: str, candidates: list[str]) -> list[tuple[str, float]]:
        if candidates == ["tag one"]:
            return [("tag one", 0.2)]
        if candidates == ["tag two"]:
            return [("tag two", 0.9)]
        return []

    mocker.patch.object(
        TagSuggester,
        "_classify_candidates",
        side_effect=classify,
    )

    result = suggester.suggest("text", candidate_tags=["tag one", "tag two"])

    assert result == ["tag-one", "tag-two"]

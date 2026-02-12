"""Tag suggestion module using NLP and zero-shot classification."""

from __future__ import annotations

import string
from collections import Counter
from pathlib import Path

try:
    import nltk
    import torch
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    from nltk.tag import pos_tag
    from nltk.tokenize import word_tokenize
    from rake_nltk import Rake
    from transformers import pipeline
except ImportError as _err:
    raise ImportError("Install buvis-pybase[ml] for NLP features: pip install buvis-pybase[ml]") from _err

MIN_KEYWORD_LENGTH = 2


class NLTKPreprocessor:
    """Handles NLTK-related preprocessing tasks."""

    @staticmethod
    def download_nltk_dependencies() -> None:
        """Download required NLTK data packages."""
        dependencies = [
            "punkt",
            "averaged_perceptron_tagger",
            "averaged_perceptron_tagger_eng",
            "stopwords",
            "wordnet",
            "omw-1.4",
            "punkt_tab",
        ]
        for dependency in dependencies:
            nltk.download(dependency, quiet=True)


class KeywordExtractor:
    """Extracts keywords from text using various methods."""

    def __init__(self: KeywordExtractor) -> None:
        self.lemmatizer = WordNetLemmatizer()
        self.rake = Rake()

    def extract_by_frequency(
        self: KeywordExtractor,
        text: str,
        count: int = 20,
    ) -> list[str]:
        """Extract keywords based on frequency of nouns."""
        tokens = word_tokenize(text.lower())
        stop_words = set(stopwords.words("english"))

        filtered_tokens = [word for word in tokens if word not in stop_words and word not in string.punctuation]

        tagged = pos_tag(filtered_tokens)
        nouns = [word for word, pos in tagged if pos.startswith("NN")]

        return [word for word, _ in Counter(nouns).most_common(count)]

    def extract_by_rake(self: KeywordExtractor, text: str) -> list[str]:
        """Extract keywords using RAKE algorithm."""
        self.rake.extract_keywords_from_text(text)
        keywords = self.rake.get_ranked_phrases()

        lemmatized = [" ".join(self.lemmatizer.lemmatize(word.lower()) for word in kw.split()) for kw in keywords]

        unique_keywords = {kw for kw in lemmatized if len(kw) >= MIN_KEYWORD_LENGTH}

        return [
            kw
            for kw in unique_keywords
            if kw.replace(" ", "").isalpha() and not any(kw != other and kw in other for other in unique_keywords)
        ]


class TagSuggester:
    """Suggests tags using zero-shot classification."""

    def __init__(
        self: TagSuggester,
        model_name: str = "facebook/bart-large-mnli",
        limit_score: float = 0.75,
    ) -> None:
        self.model_name = model_name
        self.limit_score = limit_score
        self.device = "mps" if torch.backends.mps.is_available() else 0
        self.classifier = pipeline(
            "zero-shot-classification",
            model=model_name,
            device=self.device,
        )
        self.used_tags_path = Path.home() / ".config" / "buvis" / "candidate_tags"

    def _get_used_tags(self: TagSuggester) -> list[str]:
        """Retrieve previously used tags from file."""
        return self.used_tags_path.read_text().split("\n") if self.used_tags_path.is_file() else []

    def _classify_candidates(
        self: TagSuggester,
        text: str,
        candidates: list[str],
    ) -> list[tuple[str, float]]:
        """Classify candidates using zero-shot classification."""
        if not candidates:
            return []

        result = self.classifier(
            text,
            candidate_labels=candidates,
            multi_label=True,
        )
        return list(zip(result["labels"], result["scores"]))

    def suggest(
        self: TagSuggester,
        text: str,
        candidate_tags: list[str] | None = None,
    ) -> list[str]:
        """Suggest tags for given text."""
        NLTKPreprocessor.download_nltk_dependencies()

        if not candidate_tags:
            extractor = KeywordExtractor()
            candidate_tags = list(
                set(
                    extractor.extract_by_rake(text) + extractor.extract_by_frequency(text),
                ),
            )

        used_tags = self._get_used_tags()
        top_candidates = [tag for tag in candidate_tags if tag.replace(" ", "-") in used_tags]
        bottom_candidates = [tag for tag in candidate_tags if tag.replace(" ", "-") not in used_tags]

        # Classify and combine results
        top_scores = [
            (label, score + self.limit_score) for label, score in self._classify_candidates(text, top_candidates)
        ]
        bottom_scores = self._classify_candidates(text, bottom_candidates)

        all_scores = top_scores + bottom_scores

        return [
            label.replace(" ", "-")
            for label, _ in sorted(
                [(label, score) for label, score in all_scores if score > self.limit_score],
                key=lambda x: x[1],
                reverse=True,
            )
        ]

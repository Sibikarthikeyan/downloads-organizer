"""Unit tests for extension classification and the classifier chain."""

from pathlib import Path

from downloads_organizer.classifier.base import Classification
from downloads_organizer.classifier.chain import ClassifierChain
from downloads_organizer.classifier.extension import ExtensionClassifier
from downloads_organizer.config.schema import DEFAULT_CATEGORIES


def make_classifier() -> ExtensionClassifier:
    return ExtensionClassifier(DEFAULT_CATEGORIES)


def test_common_extensions_map_to_expected_categories() -> None:
    clf = make_classifier()
    cases = {
        "report.pdf": "Documents",
        "photo.JPG": "Images",
        "movie.mkv": "Videos",
        "song.flac": "Audio",
        "bundle.zip": "Archives",
        "app.deb": "Programs",
        "script.py": "Code",
        "data.csv": "Datasets",
    }
    for name, expected in cases.items():
        result = clf.classify(Path(name))
        assert result is not None and result.category == expected, name


def test_unknown_and_missing_extensions_return_none() -> None:
    clf = make_classifier()
    assert clf.classify(Path("mystery.xyz")) is None
    assert clf.classify(Path("no_extension")) is None


def test_chain_first_match_wins_and_falls_back() -> None:
    class Always:
        def classify(self, path: Path) -> Classification:
            return Classification("First", "always")

    class Never:
        def classify(self, path: Path) -> None:
            return None

    chain = ClassifierChain([Never(), Always(), make_classifier()], fallback_category="Unknown")
    assert chain.classify(Path("a.pdf")).category == "First"

    fallback_chain = ClassifierChain([Never()], fallback_category="Unknown")
    result = fallback_chain.classify(Path("mystery.xyz"))
    assert result.category == "Unknown"


def test_chain_survives_crashing_classifier() -> None:
    class Broken:
        def classify(self, path: Path) -> Classification:
            raise RuntimeError("boom")

    chain = ClassifierChain([Broken(), make_classifier()], fallback_category="Unknown")
    assert chain.classify(Path("a.pdf")).category == "Documents"

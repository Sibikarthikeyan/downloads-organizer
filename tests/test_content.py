"""Tests for magic-byte content detection of unknown/extension-less files."""

from pathlib import Path

from downloads_organizer.classifier.content import ContentTypeClassifier
from downloads_organizer.config.schema import DEFAULT_CATEGORIES, AppConfig
from downloads_organizer.core.pipeline import OrganizerPipeline
from tests.conftest import make_file

PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def make_classifier() -> ContentTypeClassifier:
    return ContentTypeClassifier(DEFAULT_CATEGORIES)


def test_pdf_with_lying_extension(downloads: Path) -> None:
    path = make_file(downloads, "paper.weird", b"%PDF-1.7 fake body")
    result = make_classifier().classify(path)
    assert result is not None and result.category == "Documents"
    assert "content type" in result.reason


def test_png_without_extension(downloads: Path) -> None:
    path = make_file(downloads, "clipboard-image", PNG_HEADER)
    result = make_classifier().classify(path)
    assert result is not None and result.category == "Images"


def test_sqlite_routed_to_robotics_data(downloads: Path) -> None:
    path = make_file(downloads, "mapdata", b"SQLite format 3\x00" + b"\x00" * 32)
    result = make_classifier().classify(path)
    assert result is not None and result.category == "Robotics/Data"


def test_unrecognized_bytes_return_none(downloads: Path) -> None:
    path = make_file(downloads, "noise", b"\x00\x01\x02\x03nothing recognizable")
    # May be text/plain under libmagic -> Documents, or None via fallback;
    # both are acceptable, but it must never crash.
    result = make_classifier().classify(path)
    assert result is None or result.category in DEFAULT_CATEGORIES


def test_pipeline_uses_content_detection(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "mystery-download", PNG_HEADER)
    OrganizerPipeline(config).scan_existing()
    assert (downloads / "Images" / "mystery-download").is_file()


def test_content_detection_can_be_disabled(config: AppConfig, downloads: Path) -> None:
    config.content_detection = False
    make_file(downloads, "mystery-download", PNG_HEADER)
    OrganizerPipeline(config).scan_existing()
    assert (downloads / "Unknown" / "mystery-download").is_file()

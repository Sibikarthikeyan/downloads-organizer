"""Tests for source-URL routing via the browser origin xattr."""

import os
from pathlib import Path

import pytest

from downloads_organizer.config.schema import FilenameRule
from downloads_organizer.rules.url import UrlRuleClassifier
from downloads_organizer.utils.fsutils import ORIGIN_URL_XATTR
from tests.conftest import make_file

RULES = [
    FilenameRule("*arxiv.org*", "Papers"),
    FilenameRule("*github.com*", "Code"),
]


def set_origin(path: Path, url: str) -> None:
    try:
        os.setxattr(path, ORIGIN_URL_XATTR, url.encode())
    except OSError:
        pytest.skip("filesystem does not support user xattrs")


def test_url_rule_matches_origin(downloads: Path) -> None:
    path = make_file(downloads, "2406.01234.pdf")
    set_origin(path, "https://arxiv.org/pdf/2406.01234")
    result = UrlRuleClassifier(RULES).classify(path)
    assert result is not None
    assert result.category == "Papers"
    assert "arxiv.org" in result.reason


def test_file_without_xattr_falls_through(downloads: Path) -> None:
    path = make_file(downloads, "plain.pdf")
    assert UrlRuleClassifier(RULES).classify(path) is None


def test_non_matching_url_falls_through(downloads: Path) -> None:
    path = make_file(downloads, "x.bin")
    set_origin(path, "https://example.com/x.bin")
    assert UrlRuleClassifier(RULES).classify(path) is None


def test_no_rules_reads_no_xattrs(downloads: Path) -> None:
    path = make_file(downloads, "x.bin")
    assert UrlRuleClassifier([]).classify(path) is None

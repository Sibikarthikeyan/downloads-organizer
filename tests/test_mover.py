"""Unit tests for FileMover and every duplicate policy."""

import os
from pathlib import Path

from downloads_organizer.config.schema import DuplicatePolicy
from downloads_organizer.mover.mover import FileMover
from tests.conftest import make_file


def test_move_creates_destination_folder(downloads: Path) -> None:
    src = make_file(downloads, "a.pdf")
    result = FileMover(downloads).move(src, "Documents")
    assert result.moved
    assert (downloads / "Documents" / "a.pdf").is_file()
    assert not src.exists()


def test_dry_run_moves_nothing(downloads: Path) -> None:
    src = make_file(downloads, "a.pdf")
    result = FileMover(downloads, dry_run=True).move(src, "Documents")
    assert result.moved and "dry run" in result.detail
    assert src.exists()
    assert not (downloads / "Documents").exists()


def _setup_duplicate(downloads: Path) -> tuple[Path, Path]:
    existing = downloads / "Documents" / "a.pdf"
    existing.parent.mkdir()
    existing.write_bytes(b"old")
    src = make_file(downloads, "a.pdf", b"new")
    return src, existing


def test_rename_policy_keeps_both(downloads: Path) -> None:
    src, existing = _setup_duplicate(downloads)
    result = FileMover(downloads, DuplicatePolicy.RENAME).move(src, "Documents")
    assert result.moved
    assert result.destination == downloads / "Documents" / "a (1).pdf"
    assert existing.read_bytes() == b"old"
    assert result.destination.read_bytes() == b"new"


def test_skip_policy_leaves_source(downloads: Path) -> None:
    src, existing = _setup_duplicate(downloads)
    result = FileMover(downloads, DuplicatePolicy.SKIP).move(src, "Documents")
    assert not result.moved
    assert src.exists() and existing.read_bytes() == b"old"


def test_replace_policy_overwrites(downloads: Path) -> None:
    src, existing = _setup_duplicate(downloads)
    result = FileMover(downloads, DuplicatePolicy.REPLACE).move(src, "Documents")
    assert result.moved
    assert existing.read_bytes() == b"new"
    assert not src.exists()


def test_keep_newest_prefers_newer_source(downloads: Path) -> None:
    src, existing = _setup_duplicate(downloads)
    os.utime(existing, (1_000_000, 1_000_000))  # make existing much older
    result = FileMover(downloads, DuplicatePolicy.KEEP_NEWEST).move(src, "Documents")
    assert result.moved
    assert existing.read_bytes() == b"new"


def test_keep_oldest_keeps_older_target(downloads: Path) -> None:
    src, existing = _setup_duplicate(downloads)
    os.utime(existing, (1_000_000, 1_000_000))
    result = FileMover(downloads, DuplicatePolicy.KEEP_OLDEST).move(src, "Documents")
    assert not result.moved
    assert existing.read_bytes() == b"old" and src.exists()


def test_invalid_characters_are_sanitized(downloads: Path) -> None:
    src = make_file(downloads, "weird\x01name.txt")
    result = FileMover(downloads).move(src, "Documents")
    assert result.moved
    assert result.destination is not None and "\x01" not in result.destination.name

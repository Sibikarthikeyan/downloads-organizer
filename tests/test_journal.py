"""Tests for the move journal, undo, and stats."""

from pathlib import Path

from downloads_organizer.config.schema import AppConfig
from downloads_organizer.core.pipeline import OrganizerPipeline
from downloads_organizer.journal.journal import Journal, JournalEntry
from downloads_organizer.journal.stats import render_stats
from downloads_organizer.journal.undo import undo_last
from tests.conftest import make_file


def test_pipeline_records_moves_in_journal(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "photo.png", b"12345")
    OrganizerPipeline(config).scan_existing()

    entries = Journal(config.journal.path).read_all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.action == "move"
    assert entry.category == "Images"
    assert entry.size == 5
    assert Path(entry.destination) == downloads / "Images" / "photo.png"


def test_dry_run_writes_no_journal(config: AppConfig, downloads: Path) -> None:
    config.dry_run = True
    make_file(downloads, "photo.png")
    OrganizerPipeline(config).scan_existing()
    assert not config.journal.path.exists()


def test_undo_restores_last_move(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "photo.png")
    make_file(downloads, "song.mp3")
    OrganizerPipeline(config).scan_existing()
    journal = Journal(config.journal.path)

    results = undo_last(journal, 1)
    assert len(results) == 1 and results[0].restored
    # The most recent move (alphabetical scan order: song.mp3) came back.
    assert (downloads / "song.mp3").is_file()
    assert (downloads / "Images" / "photo.png").is_file()

    # Undoing again restores the other file, not the same one twice.
    results = undo_last(journal, 5)
    restored = [r for r in results if r.restored]
    assert len(restored) == 1
    assert (downloads / "photo.png").is_file()


def test_undo_skips_missing_destination(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "photo.png")
    OrganizerPipeline(config).scan_existing()
    (downloads / "Images" / "photo.png").unlink()  # user deleted it meanwhile

    results = undo_last(Journal(config.journal.path), 1)
    assert len(results) == 1 and not results[0].restored
    assert "no longer exists" in results[0].detail


def test_undo_skips_occupied_original_path(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "photo.png")
    OrganizerPipeline(config).scan_existing()
    make_file(downloads, "photo.png", b"new file with same name")

    results = undo_last(Journal(config.journal.path), 1)
    assert not results[0].restored
    assert "occupied" in results[0].detail


def test_corrupt_journal_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    good = JournalEntry.move(Path("/a/x.pdf"), Path("/a/Docs/x.pdf"), "Docs", "test", 10)
    journal = Journal(path)
    journal.record(good)
    path.write_text(path.read_text() + "{not valid json\n")
    journal.record(good)
    assert len(journal.read_all()) == 2


def test_stats_renders_summary(config: AppConfig, downloads: Path) -> None:
    make_file(downloads, "photo.png", b"abc")
    make_file(downloads, "scan.pcd", b"cloud")
    OrganizerPipeline(config).scan_existing()

    output = render_stats(Journal(config.journal.path))
    assert "Total files organized : 2" in output
    assert "Images" in output and "Robotics/PointClouds" in output
    assert ".png" in output and ".pcd" in output
    assert "photo.png -> Images" in output


def test_stats_with_empty_journal(tmp_path: Path) -> None:
    assert "empty" in render_stats(Journal(tmp_path / "none.jsonl"))

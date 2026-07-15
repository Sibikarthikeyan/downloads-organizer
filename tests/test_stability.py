"""Unit tests for download-completion detection, using a fake clock."""

from pathlib import Path

from downloads_organizer.config.schema import StabilityConfig
from downloads_organizer.watcher.stability import StabilityTracker
from tests.conftest import make_file


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_tracker(**kwargs: float) -> tuple[StabilityTracker, FakeClock]:
    clock = FakeClock()
    config = StabilityConfig(stable_seconds=3.0, max_wait_seconds=100.0, **kwargs)
    return StabilityTracker(config, clock=clock), clock


def test_stable_file_becomes_ready_after_stable_seconds(downloads: Path) -> None:
    tracker, clock = make_tracker()
    path = make_file(downloads, "a.pdf")
    tracker.add(path)
    assert tracker.collect_ready() == []
    clock.now = 3.5
    assert tracker.collect_ready() == [path]
    assert len(tracker) == 0


def test_growing_file_is_not_ready(downloads: Path) -> None:
    tracker, clock = make_tracker()
    path = make_file(downloads, "a.iso", b"x")
    tracker.add(path)
    clock.now = 2.9
    path.write_bytes(b"xx")  # still downloading
    assert tracker.collect_ready() == []
    clock.now = 4.0  # only ~1.1s since the change
    assert tracker.collect_ready() == []
    clock.now = 6.0
    assert tracker.collect_ready() == [path]


def test_temp_download_extensions_are_rejected(downloads: Path) -> None:
    tracker, _ = make_tracker()
    tracker.add(make_file(downloads, "movie.mp4.crdownload"))
    tracker.add(make_file(downloads, "doc.pdf.part"))
    assert len(tracker) == 0


def test_vanished_file_is_dropped(downloads: Path) -> None:
    tracker, clock = make_tracker()
    path = make_file(downloads, "a.pdf")
    tracker.add(path)
    path.unlink()
    clock.now = 5.0
    assert tracker.collect_ready() == []
    assert len(tracker) == 0


def test_never_stable_file_expires(downloads: Path) -> None:
    tracker, clock = make_tracker()
    path = make_file(downloads, "a.pdf", b"1")
    tracker.add(path)
    for step in range(1, 60):
        clock.now = step * 2.0
        path.write_bytes(b"1" * (step + 1))
        tracker.collect_ready()
    assert len(tracker) == 0  # gave up after max_wait_seconds


def test_placeholder_with_temp_sibling_is_rejected(downloads: Path) -> None:
    # Firefox: 0-byte placeholder next to the .part file holding the data.
    tracker, clock = make_tracker()
    placeholder = make_file(downloads, "book.xlsx", b"")
    make_file(downloads, "book.xlsx.part", b"partial data")
    tracker.add(placeholder)
    assert len(tracker) == 0
    clock.now = 10.0
    assert tracker.collect_ready() == []


def test_placeholder_ready_after_sibling_renamed_over_it(downloads: Path) -> None:
    tracker, clock = make_tracker()
    placeholder = make_file(downloads, "book.xlsx", b"")
    part = make_file(downloads, "book.xlsx.part", b"data")
    tracker.add(placeholder)  # rejected while the sibling exists
    part.rename(placeholder)  # download complete
    tracker.add(placeholder)  # re-added by the rename event
    clock.now = 3.5
    assert tracker.collect_ready() == [placeholder]


def test_sibling_appearing_after_add_blocks_readiness(downloads: Path) -> None:
    tracker, clock = make_tracker()
    placeholder = make_file(downloads, "book.xlsx", b"")
    tracker.add(placeholder)
    part = make_file(downloads, "book.xlsx.part", b"partial")  # download starts
    clock.now = 10.0
    assert tracker.collect_ready() == []
    assert len(tracker) == 1  # still pending, not dropped
    part.unlink()
    assert tracker.collect_ready() == [placeholder]


def test_repeated_add_does_not_reset_stability_clock(downloads: Path) -> None:
    tracker, clock = make_tracker()
    path = make_file(downloads, "a.pdf")
    tracker.add(path)
    clock.now = 2.0
    tracker.add(path)  # duplicate event for an unchanged file
    clock.now = 3.5
    assert tracker.collect_ready() == [path]


def test_repeated_add_preserves_first_seen_for_expiry(downloads: Path) -> None:
    clock = FakeClock()
    tracker = StabilityTracker(StabilityConfig(stable_seconds=3.0, max_wait_seconds=10.0), clock=clock)
    path = make_file(downloads, "a.iso", b"1")
    tracker.add(path)
    for step in range(1, 7):  # last step is past max_wait_seconds
        clock.now = step * 2.0
        path.write_bytes(b"1" * (step + 1))
        tracker.add(path)  # each write also produces an event
        tracker.collect_ready()
    assert len(tracker) == 0  # expiry fired despite the repeated add() calls

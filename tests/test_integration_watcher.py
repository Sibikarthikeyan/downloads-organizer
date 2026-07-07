"""Integration test: real watchdog observer on a mock Downloads folder.

Simulates a browser download: data is written to ``file.crdownload`` and
then renamed to its final name, exactly like Chrome/Firefox do.
"""

from __future__ import annotations

import time
from pathlib import Path

from downloads_organizer.config.schema import AppConfig
from downloads_organizer.core.pipeline import OrganizerPipeline
from downloads_organizer.watcher.watcher import DownloadsWatcher


def wait_for(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_simulated_browser_download_is_organized(config: AppConfig, downloads: Path) -> None:
    watcher = DownloadsWatcher(config, OrganizerPipeline(config))
    watcher.start()
    try:
        temp = downloads / "report.pdf.crdownload"
        temp.write_bytes(b"partial")
        time.sleep(0.3)
        temp.write_bytes(b"partial" * 100)  # download still in progress
        temp.rename(downloads / "report.pdf")  # download complete

        assert wait_for(lambda: (downloads / "Documents" / "report.pdf").is_file())
        assert not temp.exists()
    finally:
        watcher.stop()


def test_multiple_files_and_unknown_types(config: AppConfig, downloads: Path) -> None:
    watcher = DownloadsWatcher(config, OrganizerPipeline(config))
    watcher.start()
    try:
        (downloads / "song.mp3").write_bytes(b"a")
        (downloads / "Screenshot_001.png").write_bytes(b"b")
        (downloads / "weird.blob").write_bytes(b"c")

        assert wait_for(lambda: (downloads / "Audio" / "song.mp3").is_file())
        assert wait_for(lambda: (downloads / "Screenshots" / "Screenshot_001.png").is_file())
        assert wait_for(lambda: (downloads / "Unknown" / "weird.blob").is_file())
    finally:
        watcher.stop()


def test_watcher_stops_cleanly_when_idle(config: AppConfig, downloads: Path) -> None:
    watcher = DownloadsWatcher(config, OrganizerPipeline(config))
    watcher.start()
    watcher.stop()  # must not hang on the idle queue

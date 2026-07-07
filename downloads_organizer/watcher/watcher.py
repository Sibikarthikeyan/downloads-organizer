"""Watchdog-based watcher for the Downloads folder.

Architecture: watchdog's inotify observer thread pushes event paths onto a
queue; a single worker thread drains the queue into the
:class:`StabilityTracker` and periodically moves files the tracker declares
stable. The worker blocks on the queue when nothing is pending, so the
process is fully event-driven at idle (zero CPU between events).
"""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from downloads_organizer.config.schema import AppConfig
from downloads_organizer.core.pipeline import OrganizerPipeline
from downloads_organizer.watcher.stability import StabilityTracker

log = logging.getLogger("downloads_organizer.watcher")


class _EventHandler(FileSystemEventHandler):
    """Forward relevant top-level file events to the worker queue."""

    def __init__(self, events: "queue.Queue[Path]", watch_folder: Path) -> None:
        self._events = events
        self._watch_folder = watch_folder

    def _enqueue(self, raw_path: str | bytes) -> None:
        path = Path(raw_path if isinstance(raw_path, str) else raw_path.decode())
        # Only direct children of the watch folder; category subfolders are
        # not monitored (observer is non-recursive anyway, belt and braces).
        if path.parent == self._watch_folder:
            self._events.put(path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # A browser finishing a download renames file.crdownload -> file.
        if not event.is_directory:
            self._enqueue(event.dest_path)


class DownloadsWatcher:
    """Owns the observer, the worker thread, and the stability tracker."""

    def __init__(self, config: AppConfig, pipeline: OrganizerPipeline) -> None:
        self._config = config
        self._pipeline = pipeline
        self._events: "queue.Queue[Path | None]" = queue.Queue()
        self._tracker = StabilityTracker(config.stability)
        self._stop = threading.Event()
        self._observer = Observer()
        self._worker = threading.Thread(target=self._run_worker, name="organizer-worker", daemon=True)

    def start(self) -> None:
        watch = self._config.watch_folder
        watch.mkdir(parents=True, exist_ok=True)
        handler = _EventHandler(self._events, watch)
        self._observer.schedule(handler, str(watch), recursive=False)
        self._observer.start()
        self._worker.start()
        log.info("Watching %s", watch)

    def stop(self) -> None:
        self._stop.set()
        self._events.put(None)  # wake the worker if it is blocked on the queue
        self._observer.stop()
        self._observer.join(timeout=5)
        self._worker.join(timeout=5)

    def wait(self) -> None:
        """Block until stopped (for the CLI foreground mode)."""
        while not self._stop.is_set():
            self._stop.wait(timeout=1.0)

    # ------------------------------------------------------------------

    def _run_worker(self) -> None:
        poll = self._config.stability.poll_interval
        while not self._stop.is_set():
            # Block indefinitely when idle; poll while files are settling.
            timeout = poll if len(self._tracker) else None
            try:
                path = self._events.get(timeout=timeout)
            except queue.Empty:
                path = None
            if path is not None and self._pipeline.should_process(path):
                self._tracker.add(path)
            # Drain any burst of events without waiting.
            while True:
                try:
                    extra = self._events.get_nowait()
                except queue.Empty:
                    break
                if extra is not None and self._pipeline.should_process(extra):
                    self._tracker.add(extra)
            for ready in self._tracker.collect_ready():
                self._pipeline.process(ready)

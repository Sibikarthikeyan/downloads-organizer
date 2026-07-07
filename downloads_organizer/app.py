"""Wire config, plugins, pipeline, and watcher into a running application."""

from __future__ import annotations

import logging
import signal
from pathlib import Path

from downloads_organizer.config.loader import load_config
from downloads_organizer.config.schema import AppConfig
from downloads_organizer.core.pipeline import OrganizerPipeline
from downloads_organizer.logger.setup import setup_logging
from downloads_organizer.plugins.registry import PluginRegistry
from downloads_organizer.watcher.watcher import DownloadsWatcher

log = logging.getLogger("downloads_organizer.app")


class Application:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        setup_logging(config.logging)
        registry = PluginRegistry()
        registry.load_from_specs(config.plugins)
        self.pipeline = OrganizerPipeline(config, registry=registry)
        self.watcher = DownloadsWatcher(config, self.pipeline)

    @classmethod
    def from_config_file(cls, path: Path | None = None, **overrides: object) -> "Application":
        config = load_config(path)
        for key, value in overrides.items():
            if value is not None:
                setattr(config, key, value)
        return cls(config)

    def run_once(self) -> int:
        """Organize existing files and exit. Returns the number moved."""
        moved = self.pipeline.scan_existing()
        log.info("Organized %d file(s)", moved)
        return moved

    def run_forever(self) -> None:
        """Start watching; blocks until SIGINT/SIGTERM."""
        if self.config.organize_existing_on_start:
            # Recover files that arrived while the service was not running.
            moved = self.pipeline.scan_existing()
            if moved:
                log.info("Startup scan organized %d file(s)", moved)
        self.watcher.start()

        def _shutdown(signum: int, _frame: object) -> None:
            log.info("Received %s, shutting down", signal.Signals(signum).name)
            self.watcher.stop()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        self.watcher.wait()
        log.info("Stopped")

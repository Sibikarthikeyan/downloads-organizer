"""Decide when a file has finished downloading.

A file is *stable* when its size and mtime have not changed for
``stable_seconds``. Files with in-flight download extensions
(``.crdownload``, ``.part``, ...) are rejected outright — the browser will
rename them when the download completes, which produces a fresh event.

The tracker is passive (no threads of its own): callers add candidate paths
and periodically ask :meth:`collect_ready` which files may now be moved.
This keeps it trivially unit-testable with a fake clock.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from downloads_organizer.config.schema import StabilityConfig
from downloads_organizer.utils.fsutils import has_inflight_sibling, is_temp_download

log = logging.getLogger("downloads_organizer.watcher")


@dataclass
class _Pending:
    size: int
    mtime: float
    unchanged_since: float
    first_seen: float


class StabilityTracker:
    def __init__(self, config: StabilityConfig, clock: Callable[[], float] = time.monotonic) -> None:
        self._config = config
        self._clock = clock
        self._pending: dict[Path, _Pending] = {}

    def add(self, path: Path) -> None:
        """Register a candidate file; temp-download names are ignored."""
        if is_temp_download(path, self._config.temp_extensions):
            log.debug("Skipping in-flight download %s", path.name)
            return
        if has_inflight_sibling(path, self._config.temp_extensions):
            # Firefox-style placeholder: the real data lives in a temp
            # sibling; renaming it over the placeholder produces a fresh
            # event that re-adds the file once the download is done.
            log.debug("Skipping placeholder for in-flight download %s", path.name)
            return
        now = self._clock()
        try:
            stat = path.stat()
        except OSError:
            return  # vanished already; a later event will re-add it
        state = self._pending.get(path)
        if state is None:
            self._pending[path] = _Pending(stat.st_size, stat.st_mtime, now, now)
        elif stat.st_size != state.size or stat.st_mtime != state.mtime:
            # Keep first_seen so max_wait_seconds still applies; only the
            # stability clock restarts, and only when the file changed.
            state.size, state.mtime, state.unchanged_since = stat.st_size, stat.st_mtime, now

    def discard(self, path: Path) -> None:
        self._pending.pop(path, None)

    def __len__(self) -> int:
        return len(self._pending)

    def collect_ready(self) -> list[Path]:
        """Return files stable for ``stable_seconds``; drop vanished/expired ones."""
        now = self._clock()
        ready: list[Path] = []
        for path, state in list(self._pending.items()):
            try:
                stat = path.stat()
            except OSError:
                del self._pending[path]
                continue
            if stat.st_size != state.size or stat.st_mtime != state.mtime:
                state.size, state.mtime, state.unchanged_since = stat.st_size, stat.st_mtime, now
            if has_inflight_sibling(path, self._config.temp_extensions):
                # A temp sibling appeared after add(); the file is a
                # placeholder for a download still in progress.
                if now - state.first_seen > self._config.max_wait_seconds:
                    log.warning("Giving up on placeholder %s", path)
                    del self._pending[path]
                continue
            if now - state.unchanged_since >= self._config.stable_seconds:
                ready.append(path)
                del self._pending[path]
            elif now - state.first_seen > self._config.max_wait_seconds:
                log.warning("Giving up on unstable file %s", path)
                del self._pending[path]
        return ready

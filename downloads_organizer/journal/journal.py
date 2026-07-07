"""Append-only JSONL journal of every move the organizer performs.

One JSON object per line keeps writes atomic-enough (single ``write`` of a
short line with O_APPEND) and the file greppable/human-readable. Corrupt
lines are skipped on read so a partial write can never break undo/stats.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("downloads_organizer.journal")


@dataclass(frozen=True)
class JournalEntry:
    timestamp: str
    #: "move" for organizer actions, "undo" for reversals.
    action: str
    source: str
    destination: str
    category: str
    reason: str
    size: int

    @classmethod
    def move(cls, source: Path, destination: Path, category: str, reason: str, size: int) -> "JournalEntry":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            action="move",
            source=str(source),
            destination=str(destination),
            category=category,
            reason=reason,
            size=size,
        )

    @classmethod
    def undo(cls, original: "JournalEntry") -> "JournalEntry":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            action="undo",
            source=original.destination,
            destination=original.source,
            category=original.category,
            reason=f"undo of move at {original.timestamp}",
            size=original.size,
        )


class Journal:
    def __init__(self, path: Path, enabled: bool = True) -> None:
        self._path = path
        self._enabled = enabled

    @property
    def path(self) -> Path:
        return self._path

    def record(self, entry: JournalEntry) -> None:
        if not self._enabled:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry)) + "\n")
        except OSError as exc:
            log.error("Could not write journal entry: %s", exc)

    def read_all(self) -> list[JournalEntry]:
        """All valid entries, oldest first. Corrupt lines are skipped."""
        if not self._path.is_file():
            return []
        entries: list[JournalEntry] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(JournalEntry(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                log.warning("Skipping corrupt journal line: %.80s", line)
        return entries

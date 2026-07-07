"""Reverse the most recent moves recorded in the journal."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from downloads_organizer.journal.journal import Journal, JournalEntry

log = logging.getLogger("downloads_organizer.journal")


@dataclass(frozen=True)
class UndoResult:
    entry: JournalEntry
    restored: bool
    detail: str


def undo_last(journal: Journal, count: int = 1) -> list[UndoResult]:
    """Undo up to ``count`` of the most recent not-yet-undone moves.

    A move is skipped (never guessed at) when the organized file no longer
    exists at its destination or the original path is occupied again.
    """
    entries = journal.read_all()
    undone_destinations = {e.source for e in entries if e.action == "undo"}
    results: list[UndoResult] = []

    for entry in reversed(entries):
        if len(results) >= count:
            break
        if entry.action != "move" or entry.destination in undone_destinations:
            continue
        results.append(_restore(journal, entry))
        undone_destinations.add(entry.destination)
    return results


def _restore(journal: Journal, entry: JournalEntry) -> UndoResult:
    destination = Path(entry.destination)
    original = Path(entry.source)
    if not destination.is_file():
        return UndoResult(entry, False, f"{destination} no longer exists")
    if original.exists():
        return UndoResult(entry, False, f"original path {original} is occupied")
    try:
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(destination), str(original))
    except OSError as exc:
        return UndoResult(entry, False, f"restore failed: {exc}")
    journal.record(JournalEntry.undo(entry))
    log.info("Restored %s -> %s", destination, original)
    return UndoResult(entry, True, f"restored to {original}")

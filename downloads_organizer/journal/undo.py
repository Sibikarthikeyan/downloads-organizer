"""Reverse the most recent moves recorded in the journal."""

from __future__ import annotations

import logging
import shutil
from collections import Counter
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
    results: list[UndoResult] = []
    # Walking newest-first, each undo entry cancels out the nearest earlier
    # move to the same destination. A plain set would mark a destination as
    # undone forever, breaking undo once a file is re-organized to it.
    undo_credits: Counter[str] = Counter()

    for entry in reversed(entries):
        if len(results) >= count:
            break
        if entry.action == "undo":
            undo_credits[entry.source] += 1
            continue
        if entry.action != "move":
            continue
        if undo_credits[entry.destination] > 0:
            undo_credits[entry.destination] -= 1
            continue
        results.append(_restore(journal, entry))
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
